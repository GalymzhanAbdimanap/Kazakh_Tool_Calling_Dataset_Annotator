import streamlit as st
import sqlite3
import json
import hashlib
import pandas as pd
from datetime import datetime

# --- КОНФИГУРАЦИЯ И БАЗА ДАННЫХ ---
DB_FILE = "kazakh_tool_dataset.db"

# --- ФУНКЦИИ БЕЗОПАСНОСТИ ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Таблица аннотаций
    c.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id TEXT PRIMARY KEY,
            category TEXT,
            difficulty TEXT,
            query TEXT,
            tools_json TEXT,
            answers_json TEXT,
            turns_json TEXT,
            author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        c.execute("ALTER TABLE annotations ADD COLUMN author TEXT")
    except sqlite3.OperationalError:
        pass

    # 2. Таблица пользователей
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    ''')
    
    c.execute('SELECT * FROM users')
    if not c.fetchall():
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                  ('admin', make_hashes('admin123')))
    
    conn.commit()
    conn.close()

# --- ФУНКЦИИ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ---
def create_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username, password) VALUES (?,?)', 
                  (username, make_hashes(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    data = c.fetchall()
    conn.close()
    if data:
        return check_hashes(password, data[0][0])
    return False

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username FROM users')
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return data

def update_user_password(username, new_password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE users SET password = ? WHERE username = ?', 
              (make_hashes(new_password), username))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ СОХРАНЕНИЯ ---
def save_to_db(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO annotations 
        (id, category, difficulty, query, tools_json, answers_json, turns_json, author)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['id'], 
        data['category'], 
        data['difficulty'], 
        data['query'],
        json.dumps(data['tools'], ensure_ascii=False),
        json.dumps(data['answers'], ensure_ascii=False),
        json.dumps(data['turns'], ensure_ascii=False),
        data.get('author', 'unknown')
    ))
    conn.commit()
    conn.close()

# --- БИБЛИОТЕКА ИНСТРУМЕНТОВ ---
def get_tool_library():
    return {
        # === ПОГОДА ===
        "weather.get": {
            "name": "weather.get",
            "description": "Get current weather conditions for a city",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "units": {"type": "string", "description": "metric or imperial", "required": False}
            }
        },
        "weather.forecast": {
            "name": "weather.forecast",
            "description": "Get weather forecast for upcoming days",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "days": {"type": "int", "description": "Number of days (1-7)", "required": False}
            }
        },
        "air.quality": {
            "name": "air.quality",
            "description": "Get air quality index and pollution levels",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True}
            }
        },
        # === КАРТЫ ===
        "maps.geocode": {
            "name": "maps.geocode",
            "description": "Convert address to latitude/longitude coordinates",
            "parameters": {
                "address": {"type": "string", "description": "Full address or location name", "required": True}
            }
        },
        "maps.route": {
            "name": "maps.route",
            "description": "Calculate driving/walking route between locations",
            "parameters": {
                "from": {"type": "string", "description": "Starting location", "required": True},
                "to": {"type": "string", "description": "Destination", "required": True},
                "mode": {"type": "string", "description": "driving, walking, transit", "required": False}
            }
        },
        # === ПУТЕШЕСТВИЯ ===
        "flights.search": {
            "name": "flights.search",
            "description": "Search available flights between airports",
            "parameters": {
                "from": {"type": "string", "description": "Departure airport code", "required": True},
                "to": {"type": "string", "description": "Arrival airport code", "required": True},
                "date": {"type": "string", "description": "Departure date YYYY-MM-DD", "required": True},
                "sort": {"type": "string", "description": "price, duration, departure_time", "required": False}
            }
        },
        "flights.book": {
            "name": "flights.book",
            "description": "Book a specific flight",
            "parameters": {
                "flightId": {"type": "string", "description": "Flight ID from search", "required": True},
                "passengerName": {"type": "string", "description": "Passenger full name", "required": True},
                "phone": {"type": "string", "description": "Contact phone", "required": False}
            }
        },
        "hotels.search": {
            "name": "hotels.search",
            "description": "Search hotels in a city",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "checkin": {"type": "string", "description": "Check-in date YYYY-MM-DD", "required": True},
                "nights": {"type": "int", "description": "Number of nights", "required": False}
            }
        },
        "hotels.book": {
            "name": "hotels.book",
            "description": "Book a hotel room",
            "parameters": {
                "hotelId": {"type": "string", "description": "Hotel ID from search", "required": True},
                "checkin": {"type": "string", "description": "Check-in date YYYY-MM-DD", "required": True},
                "nights": {"type": "int", "description": "Number of nights", "required": True},
                "guestName": {"type": "string", "description": "Guest name", "required": True}
            }
        },
        "trains.search": {
            "name": "trains.search",
            "description": "Search train schedules",
            "parameters": {
                "from": {"type": "string", "description": "Departure station", "required": True},
                "to": {"type": "string", "description": "Arrival station", "required": True},
                "date": {"type": "string", "description": "Travel date YYYY-MM-DD", "required": True}
            }
        },
        # === КАЛЕНДАРЬ ===
        "calendar.get": {
            "name": "calendar.get",
            "description": "Get calendar events for a specific date",
            "parameters": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD", "required": True},
                "timezone": {"type": "string", "description": "Timezone like Asia/Almaty", "required": False}
            }
        },
        "calendar.add": {
            "name": "calendar.add",
            "description": "Add new calendar event",
            "parameters": {
                "title": {"type": "string", "description": "Event title", "required": True},
                "datetime": {"type": "string", "description": "Start time RFC3339", "required": True},
                "duration": {"type": "int", "description": "Duration in minutes", "required": False},
                "location": {"type": "string", "description": "Event location", "required": False}
            }
        },
        # === КОММУНИКАЦИЯ ===
        "email.send": {
            "name": "email.send",
            "description": "Send email message",
            "parameters": {
                "to": {"type": "string", "description": "Recipient email", "required": True},
                "subject": {"type": "string", "description": "Email subject", "required": True},
                "body": {"type": "string", "description": "Email content", "required": True}
            }
        },
        "sms.send": {
            "name": "sms.send",
            "description": "Send SMS message",
            "parameters": {
                "to": {"type": "string", "description": "Phone number", "required": True},
                "message": {"type": "string", "description": "SMS text", "required": True}
            }
        },
        # === ПОИСК ===
        "web.search": {
            "name": "web.search",
            "description": "Search the web for information",
            "parameters": {
                "query": {"type": "string", "description": "Search query", "required": True},
                "limit": {"type": "int", "description": "Number of results", "required": False}
            }
        },
        "news.search": {
            "name": "news.search",
            "description": "Search recent news articles",
            "parameters": {
                "query": {"type": "string", "description": "Search topic", "required": True},
                "language": {"type": "string", "description": "Language code", "required": False},
                "pageToken": {"type": "string", "description": "Pagination token", "required": False}
            }
        },
        "wiki.search": {
            "name": "wiki.search",
            "description": "Search Wikipedia articles",
            "parameters": {
                "query": {"type": "string", "description": "Search term", "required": True},
                "language": {"type": "string", "description": "Language code like kk, ru, en", "required": False}
            }
        },
        # === ФИНАНСЫ ===
        "forex.rate": {
            "name": "forex.rate",
            "description": "Get currency exchange rate",
            "parameters": {
                "from": {"type": "string", "description": "Source currency code", "required": True},
                "to": {"type": "string", "description": "Target currency code", "required": True}
            }
        },
        "bank.balance": {
            "name": "bank.balance",
            "description": "Get bank account balance",
            "parameters": {
                "account": {"type": "string", "description": "Account number", "required": True},
                "api_key": {"type": "string", "description": "Auth key", "required": False}
            }
        },
        "bank.transfer": {
            "name": "bank.transfer",
            "description": "Transfer money between accounts",
            "parameters": {
                "from_account": {"type": "string", "description": "Source account", "required": True},
                "to_account": {"type": "string", "description": "Destination account", "required": True},
                "amount": {"type": "float", "description": "Amount to transfer", "required": True},
                "api_key": {"type": "string", "description": "Auth key", "required": True}
            }
        },
        "crypto.price": {
            "name": "crypto.price",
            "description": "Get cryptocurrency price",
            "parameters": {
                "symbol": {"type": "string", "description": "Crypto symbol like BTC, ETH", "required": True},
                "currency": {"type": "string", "description": "Target currency like USD, KZT", "required": False}
            }
        },
        # === ПОКУПКИ ===
        "shop.search": {
            "name": "shop.search",
            "description": "Search products in online store",
            "parameters": {
                "query": {"type": "string", "description": "Product search query", "required": True},
                "category": {"type": "string", "description": "Product category", "required": False},
                "sort": {"type": "string", "description": "price_low, price_high, rating", "required": False}
            }
        },
        "shop.add_to_cart": {
            "name": "shop.add_to_cart",
            "description": "Add product to shopping cart",
            "parameters": {
                "productId": {"type": "string", "description": "Product ID", "required": True},
                "quantity": {"type": "int", "description": "Number of items", "required": False}
            }
        },
        "shop.checkout": {
            "name": "shop.checkout",
            "description": "Complete purchase",
            "parameters": {
                "cartId": {"type": "string", "description": "Shopping cart ID", "required": True},
                "paymentMethod": {"type": "string", "description": "card, cash, bank_transfer", "required": True}
            }
        },
        # === ДОКУМЕНТАЦИЯ ===
        "docs.retrieve": {
            "name": "docs.retrieve",
            "description": "Get API documentation for a service",
            "parameters": {
                "service": {"type": "string", "description": "Service name", "required": True},
                "function": {"type": "string", "description": "Function name", "required": True}
            }
        },
        # === АНАЛИЗ ТЕКСТА ===
        "nlp.sentiment": {
            "name": "nlp.sentiment",
            "description": "Analyze sentiment of text",
            "parameters": {
                "text": {"type": "string", "description": "Text to analyze", "required": True},
                "language": {"type": "string", "description": "Language code", "required": False}
            }
        },
        "nlp.translate": {
            "name": "nlp.translate",
            "description": "Translate text between languages",
            "parameters": {
                "text": {"type": "string", "description": "Text to translate", "required": True},
                "from_lang": {"type": "string", "description": "Source language", "required": True},
                "to_lang": {"type": "string", "description": "Target language", "required": True}
            }
        },
        # === СЕТЬ И СИСТЕМА ===
        "network.speedtest": {
            "name": "network.speedtest",
            "description": "Test internet connection speed",
            "parameters": {
                "server": {"type": "string", "description": "Test server location", "required": False}
            }
        },
        "system.time": {
            "name": "system.time",
            "description": "Get current time in timezone",
            "parameters": {
                "timezone": {"type": "string", "description": "Timezone like Asia/Almaty", "required": True}
            }
        },
        # === МЕДИА ===
        "images.search": {
            "name": "images.search",
            "description": "Search for images",
            "parameters": {
                "query": {"type": "string", "description": "Image search query", "required": True},
                "limit": {"type": "int", "description": "Number of results", "required": False}
            }
        },
        "video.search": {
            "name": "video.search",
            "description": "Search for videos",
            "parameters": {
                "query": {"type": "string", "description": "Video search query", "required": True},
                "platform": {"type": "string", "description": "youtube, vimeo, all", "required": False}
            }
        },
        # === СОБЫТИЯ ===
        "events.search": {
            "name": "events.search",
            "description": "Search for events in a city",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "type": {"type": "string", "description": "concert, sports, theater, etc", "required": False},
                "date": {"type": "string", "description": "Event date YYYY-MM-DD", "required": False}
            }
        },
        "tickets.book": {
            "name": "tickets.book",
            "description": "Book event tickets",
            "parameters": {
                "eventId": {"type": "string", "description": "Event ID from search", "required": True},
                "quantity": {"type": "int", "description": "Number of tickets", "required": True},
                "seatType": {"type": "string", "description": "vip, regular, balcony", "required": False}
            }
        },
        "restaurant.search": {
            "name": "restaurant.search",
            "description": "Search restaurants",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "cuisine": {"type": "string", "description": "Cuisine type", "required": False},
                "priceRange": {"type": "string", "description": "budget, mid, expensive", "required": False}
            }
        },
        "restaurant.reserve": {
            "name": "restaurant.reserve",
            "description": "Make restaurant reservation",
            "parameters": {
                "restaurantId": {"type": "string", "description": "Restaurant ID", "required": True},
                "date": {"type": "string", "description": "Reservation date YYYY-MM-DD", "required": True},
                "time": {"type": "string", "description": "Time HH:MM", "required": True},
                "guests": {"type": "int", "description": "Number of guests", "required": True}
            }
        }
    }

# --- UI ИНТЕРФЕЙС ---
st.set_page_config(page_title="Kazakh Tool-Call Annotator", layout="wide")
init_db()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

if 'tool_steps' not in st.session_state:
    st.session_state['tool_steps'] = [{"id": 0}] 
if 'step_counter' not in st.session_state:
    st.session_state['step_counter'] = 1

# === ЛОГИКА АВТОРИЗАЦИИ ===
if not st.session_state['logged_in']:
    st.title("🔐 Авторизация")
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type='password')
        if st.button("Войти"):
            if login_user(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
    # st.info("По умолчанию: admin / admin123")
    st.stop()

# === ОСНОВНОЕ ПРИЛОЖЕНИЕ ===
st.sidebar.markdown(f"👤 Пользователь: **{st.session_state['username']}**")
if st.sidebar.button("Выйти"):
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.rerun()

st.title("🇰🇿 Kazakh Tool-Calling Dataset Annotator")
st.markdown("Инструмент для создания датасета согласно методологии APIGen.")

menu_options = ["Аннотация (Добавить данные)", "Экспорт (Скачать JSON)"]
if st.session_state['username'] == 'admin':
    menu_options.append("Управление пользователями")

page = st.sidebar.radio("Меню", menu_options)

# === СТРАНИЦА УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ===
if page == "Управление пользователями":
    if st.session_state['username'] != 'admin':
        st.error("У вас нет прав доступа к этой странице.")
        st.stop()

    st.header("Управление пользователями")
    tab1, tab2 = st.tabs(["Создать нового", "Редактировать пароль"])
    
    with tab1:
        st.subheader("Создать пользователя")
        with st.form("create_user_form"):
            new_user = st.text_input("Новый логин")
            new_pass = st.text_input("Новый пароль", type='password')
            submitted = st.form_submit_button("Создать")
            if submitted:
                if len(new_user) > 0 and len(new_pass) > 0:
                    if create_user(new_user, new_pass):
                        st.success(f"Пользователь {new_user} успешно создан")
                    else:
                        st.error("Пользователь с таким именем уже существует")
                else:
                    st.warning("Заполните все поля")

    with tab2:
        st.subheader("Сменить пароль")
        all_users = get_all_users()
        selected_user = st.selectbox("Выберите пользователя", all_users)
        new_pass_edit = st.text_input("Новый пароль для пользователя", type='password', key="edit_pass")
        if st.button("Обновить пароль"):
            if len(new_pass_edit) > 0:
                update_user_password(selected_user, new_pass_edit)
                st.success(f"Пароль для {selected_user} обновлен")
            else:
                st.warning("Введите новый пароль")

# === СТРАНИЦА АННОТАЦИИ ===
elif page == "Аннотация (Добавить данные)":
    st.header("Новая запись")

    # 1. Метаданные
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Категория (Category)", [
            "tool_awareness", 
            "planning_multistep", 
            "api_discovery", 
            "argument_schema", 
            "state_context", 
            "exception_handling", 
            "answer_synthesis"
        ])
    with col2:
        difficulty = st.selectbox("Сложность (Difficulty)", ["easy", "hard"])

    sample_id = st.text_input("ID образца", value=f"kk_{category}_001")

    # 2. Запрос
    query = st.text_area("Запрос пользователя (на казахском)", 
                         placeholder="Стамбул туралы көп фотосурет іздеңіз.",
                         help="Используйте культурный контекст.")

    # 3. Выбор инструментов
    st.subheader("🛠 Выбор доступных инструментов")
    tool_lib = get_tool_library()
    selected_tool_names = st.multiselect("Выберите доступные инструменты для этого диалога", 
                                         options=list(tool_lib.keys()))
    
    selected_tools_objs = [tool_lib[name] for name in selected_tool_names]
    st.json(selected_tools_objs, expanded=False)

    # 4. Диалог (Turns)
    st.subheader("💬 Диалог (Turns)")
    st.info("Формат цепочки: [Мысль (Plan) -> Инструмент -> Ответ] повторяется для каждого шага.")
    
    # Кнопки управления шагами
    col_b1, col_b2 = st.columns([1, 5])
    with col_b1:
        if st.button("➕ Добавить шаг"):
            st.session_state['tool_steps'].append({"id": st.session_state['step_counter']})
            st.session_state['step_counter'] += 1
    with col_b2:
        if st.button("➖ Удалить последний") and len(st.session_state['tool_steps']) > 0:
            st.session_state['tool_steps'].pop()

    # Рендеринг шагов
    steps_data = [] 
    
    for i, step in enumerate(st.session_state['tool_steps']):
        st.markdown(f"---")
        st.subheader(f"Шаг {i+1}")
        
        # 1. МЫСЛИ (Теперь внутри каждого шага)
        st.markdown("**1. Мысль перед действием**")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            step_plan = st.text_input(
                f"Assistant Plan (Meta) #{i+1}", 
                placeholder="Retry with lower limit" if i > 0 else "Search for images",
                key=f"plan_{step['id']}"
            )
        with col_t2:
            step_thought = st.text_input(
                f"Мысль ассистента (на казахском) #{i+1}", 
                placeholder="Сұрау шегі асты, азырақ сурет сұрап қайталаймын." if i > 0 else "Сурет іздеу қызметін пайдаланып көремін.",
                key=f"thought_{step['id']}"
            )

        # 2. ИНСТРУМЕНТ
        st.markdown("**2. Вызов и Результат**")
        c1, c2 = st.columns([1, 1])
        
        with c1:
            step_tool = st.selectbox(
                f"Инструмент #{i+1}", 
                ["(Нет вызова)"] + selected_tool_names,
                key=f"tool_select_{step['id']}"
            )
            
            default_json_val = "{}"
            if step_tool != "(Нет вызова)":
                current_tool_def = tool_lib[step_tool]
                params_schema = current_tool_def.get("parameters", {})
                arg_template = {}
                for param_name, param_details in params_schema.items():
                    p_type = param_details.get("type", "string")
                    is_req = " (обязательно)" if param_details.get("required") else ""
                    arg_template[param_name] = f"<{p_type}>{is_req}"
                default_json_val = json.dumps(arg_template, indent=4, ensure_ascii=False)

            step_args = st.text_area(
                f"Аргументы #{i+1} (JSON)", 
                value=default_json_val, 
                height=200,
                key=f"args_{step['id']}"
            )

        with c2:
            step_output = st.text_area(
                f"Результат API #{i+1} (JSON)", 
                value='{"error": "rate_limit_exceeded"}' if i == 0 and category == "exception_handling" else '{}',
                height=268,
                key=f"output_{step['id']}"
            )

        steps_data.append({
            "tool": step_tool,
            "args": step_args,
            "output": step_output,
            "plan": step_plan,
            "thought": step_thought
        })

    st.markdown("---")
    # 3. Финал
    st.subheader("🏁 Итоговый ответ")
    final_answer = st.text_area("Финальный ответ (на казахском)", 
                                placeholder="Стамбул суреттері табылды: Айя София және басқалары.")

    # --- СОХРАНЕНИЕ ---
    if st.button("Сохранить в БД", type="primary"):
        if not query:
            st.error("Введите запрос пользователя!")
        else:
            turns = []
            answers = [] 
            
            # 1. User
            turns.append({"role": "user", "content": query})
            
            # 2. Loop through Steps (Thought -> Call -> Output)
            valid_steps = True
            for step in steps_data:
                t_name = step['tool']
                t_args_str = step['args']
                t_out_str = step['output']
                t_plan = step['plan']
                t_thought = step['thought']
                
                # ВСЕГДА добавляем мысль, если она заполнена (даже если нет вызова инструмента, например для размышлений)
                # Но по стандарту APIGen обычно мысль идет перед тулом.
                if t_thought or t_plan:
                     turns.append({
                        "role": "assistant",
                        "content": t_thought if t_thought else "...",
                        "meta": {"plan": t_plan if t_plan else ""}
                    })

                if t_name != "(Нет вызова)":
                    try:
                        args_json = json.loads(t_args_str)
                        # Tool Call
                        turns.append({
                            "role": "assistant",
                            "tool_call": {
                                "name": t_name,
                                "arguments": args_json
                            }
                        })
                        
                        # Tool Output
                        turns.append({
                            "role": "tool",
                            "content": t_out_str
                        })
                        
                        answers.append({"name": t_name, "arguments": args_json})
                        
                    except json.JSONDecodeError:
                        st.error(f"Ошибка JSON в шаге с инструментом {t_name}")
                        valid_steps = False
                        break
            
            if valid_steps:
                # 3. Final Answer
                turns.append({"role": "assistant", "content": final_answer})

                data_obj = {
                    "id": sample_id,
                    "category": category,
                    "difficulty": difficulty,
                    "query": query,
                    "tools": selected_tools_objs,
                    "answers": answers,
                    "turns": turns,
                    "author": st.session_state['username']
                }
                
                save_to_db(data_obj)
                st.success(f"Запись {sample_id} успешно сохранена! Шагов: {len(steps_data)}")

# === ЭКСПОРТ ===
elif page == "Экспорт (Скачать JSON)":
    st.header("Экспорт данных")
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM annotations", conn)
    conn.close()
    st.dataframe(df)
    categories = df['category'].unique().tolist()
    if categories:
        selected_cat = st.selectbox("Выберите категорию для скачивания", categories)
        if st.button("Сгенерировать JSON файл"):
            subset = df[df['category'] == selected_cat]
            final_json_list = []
            for index, row in subset.iterrows():
                try:
                    tools_obj = json.loads(row['tools_json'])
                    answers_obj = json.loads(row['answers_json'])
                    turns_obj = json.loads(row['turns_json'])
                    item = {
                        "id": row['id'],
                        "category": row['category'],
                        "difficulty": row['difficulty'],
                        "query": row['query'],
                        "tools": json.dumps(tools_obj, ensure_ascii=False),
                        "answers": json.dumps(answers_obj, ensure_ascii=False),
                        "turns": turns_obj 
                    }
                    final_json_list.append(item)
                except Exception as e:
                    st.error(f"Ошибка при обработке ID {row['id']}: {e}")
            json_str = json.dumps(final_json_list, indent=4, ensure_ascii=False)
            fname = f"{selected_cat}.json"
            st.download_button(label=f"Скачать {fname}", data=json_str, file_name=fname, mime="application/json")
            st.success(f"Готово к скачиванию!")
    else:
        st.info("База данных пуста.")
