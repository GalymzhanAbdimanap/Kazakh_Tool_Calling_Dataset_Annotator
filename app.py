import streamlit as st
import sqlite3
import json
import hashlib
import pandas as pd
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
DB_FILE = "kazakh_tool_dataset.db"
st.set_page_config(page_title="Kazakh Annotator Pro", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'tool_steps' not in st.session_state: st.session_state['tool_steps'] = [{"id": 0}]
if 'step_counter' not in st.session_state: st.session_state['step_counter'] = 1

# --- БАЗА ДАННЫХ ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS annotations (
            id TEXT PRIMARY KEY, category TEXT, difficulty TEXT, query TEXT,
            tools_json TEXT, answers_json TEXT, turns_json TEXT, author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
        c.execute('SELECT * FROM users WHERE username="admin"')
        if not c.fetchone():
            c.execute('INSERT INTO users VALUES (?, ?)', ('admin', make_hashes('admin123')))
        conn.commit()

init_db()

@st.cache_data(ttl=10) # Быстрая проверка существующих ID
def get_existing_ids():
    with sqlite3.connect(DB_FILE) as conn:
        return {row[0] for row in conn.execute("SELECT id FROM annotations").fetchall()}

@st.cache_data
def get_tool_library():
    # Используем ваш полный словарь инструментов
    return {
        # === ПОГОДА ===
        "weather.get": {
            "name": "weather.get",
            "description": "Get current weather conditions for a city",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "units": {"type": "string", "description": "metric or imperial", "required": False}
            },
            "mock_response": {
                "temperature": None,  # Цифра -> null
                "feels_like": None,   # Цифра -> null
                "condition": "",      # Строка -> ""
                "humidity": None,     # Цифра -> null
                "wind_kph": None,     # Цифра -> null
                "city": ""            # Строка -> ""
            }
        },
        "weather.forecast": {
            "name": "weather.forecast",
            "description": "Get weather forecast for upcoming days",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "days": {"type": "int", "description": "Number of days (1-7)", "required": False}
            },
            "mock_response": {
                "city": "",
                "forecast": [
                    {
                        "date": "", 
                        "temp_max": None, 
                        "temp_min": None, 
                        "condition": ""
                    }
                ]
            }
        },
        "air.quality": {
            "name": "air.quality",
            "description": "Get air quality index and pollution levels",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True}
            },
            "mock_response": {
                "aqi": None,
                "level": "",
                "dominant_pollutant": "",
                "recommendation": ""
            }
        },
        # === КАРТЫ ===
        "maps.geocode": {
            "name": "maps.geocode",
            "description": "Convert address to latitude/longitude coordinates",
            "parameters": {
                "address": {"type": "string", "description": "Full address or location name", "required": True}
            },
            "mock_response": {
                "lat": None,
                "lon": None,
                "formatted_address": ""
            }
        },
        "maps.route": {
            "name": "maps.route",
            "description": "Calculate driving/walking route between locations",
            "parameters": {
                "from": {"type": "string", "description": "Starting location", "required": True},
                "to": {"type": "string", "description": "Destination", "required": True},
                "mode": {"type": "string", "description": "driving, walking, transit", "required": False}
            },
            "mock_response": {
                "distance_km": None,
                "duration_min": None,
                "traffic_condition": "",
                "route_summary": ""
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
            },
            "mock_response": {
                "flights": [
                    {
                        "airline": "", 
                        "flight_no": "", 
                        "price_kzt": None, 
                        "departure": "", 
                        "arrival": ""
                    }
                ]
            }
        },
        "flights.book": {
            "name": "flights.book",
            "description": "Book a specific flight",
            "parameters": {
                "flightId": {"type": "string", "description": "Flight ID from search", "required": True},
                "passengerName": {"type": "string", "description": "Passenger full name", "required": True},
                "phone": {"type": "string", "description": "Contact phone", "required": False}
            },
            "mock_response": {
                "booking_id": "",
                "status": "",
                "pnr": "",
                "ticket_url": ""
            }
        },
        "hotels.search": {
            "name": "hotels.search",
            "description": "Search hotels in a city",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "checkin": {"type": "string", "description": "Check-in date YYYY-MM-DD", "required": True},
                "nights": {"type": "int", "description": "Number of nights", "required": False}
            },
            "mock_response": {
                "results": [
                    {
                        "id": "", 
                        "name": "", 
                        "stars": None, 
                        "price_per_night": None, 
                        "rating": None
                    }
                ]
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
            },
            "mock_response": {
                "reservation_id": "",
                "status": "",
                "hotel_name": "",
                "total_price": None
            }
        },
        "trains.search": {
            "name": "trains.search",
            "description": "Search train schedules",
            "parameters": {
                "from": {"type": "string", "description": "Departure station", "required": True},
                "to": {"type": "string", "description": "Arrival station", "required": True},
                "date": {"type": "string", "description": "Travel date YYYY-MM-DD", "required": True}
            },
            "mock_response": {
                "trains": [
                    {
                        "number": "", 
                        "type": "", 
                        "departure": "", 
                        "arrival": "", 
                        "price_coupe": None,
                        "price_platz": None
                    }
                ]
            }
        },
        # === КАЛЕНДАРЬ ===
        "calendar.get": {
            "name": "calendar.get",
            "description": "Get calendar events for a specific date",
            "parameters": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD", "required": True},
                "timezone": {"type": "string", "description": "Timezone like Asia/Almaty", "required": False}
            },
            "mock_response": {
                "date": "",
                "events": [
                    {
                        "id": "", 
                        "time": "", 
                        "title": "", 
                        "location": ""
                    }
                ]
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
            },
            "mock_response": {
                "status": "",
                "event_id": "",
                "link": ""
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
            },
            "mock_response": {
                "status": "",
                "message_id": "",
                "timestamp": ""
            }
        },
        "sms.send": {
            "name": "sms.send",
            "description": "Send SMS message",
            "parameters": {
                "to": {"type": "string", "description": "Phone number", "required": True},
                "message": {"type": "string", "description": "SMS text", "required": True}
            },
            "mock_response": {
                "status": "",
                "segments": None,
                "cost": None
            }
        },
        # === ПОИСК ===
        "web.search": {
            "name": "web.search",
            "description": "Search the web for information",
            "parameters": {
                "query": {"type": "string", "description": "Search query", "required": True},
                "limit": {"type": "int", "description": "Number of results", "required": False}
            },
            "mock_response": {
                "results": [
                    {
                        "title": "", 
                        "snippet": "", 
                        "url": ""
                    }
                ]
            }
        },
        "news.search": {
            "name": "news.search",
            "description": "Search recent news articles",
            "parameters": {
                "query": {"type": "string", "description": "Search topic", "required": True},
                "language": {"type": "string", "description": "Language code", "required": False},
                "pageToken": {"type": "string", "description": "Pagination token", "required": False}
            },
            "mock_response": {
                "articles": [
                    {
                        "source": "", 
                        "title": "", 
                        "date": "", 
                        "url": ""
                    }
                ]
            }
        },
        "wiki.search": {
            "name": "wiki.search",
            "description": "Search Wikipedia articles",
            "parameters": {
                "query": {"type": "string", "description": "Search term", "required": True},
                "language": {"type": "string", "description": "Language code like kk, ru, en", "required": False}
            },
            "mock_response": {
                "title": "",
                "summary": "",
                "page_url": ""
            }
        },
        # === ФИНАНСЫ ===
        "forex.rate": {
            "name": "forex.rate",
            "description": "Get currency exchange rate",
            "parameters": {
                "from": {"type": "string", "description": "Source currency code", "required": True},
                "to": {"type": "string", "description": "Target currency code", "required": True}
            },
            "mock_response": {
                "from": "",
                "to": "",
                "rate": None,
                "updated": ""
            }
        },
        "bank.balance": {
            "name": "bank.balance",
            "description": "Get bank account balance",
            "parameters": {
                "account": {"type": "string", "description": "Account number", "required": True},
                "api_key": {"type": "string", "description": "Auth key", "required": False}
            },
            "mock_response": {
                "account": "",
                "balance": None,
                "currency": ""
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
            },
            "mock_response": {
                "transaction_id": "",
                "status": "",
                "amount": None,
                "currency": "",
                "remaining_balance": None
            }
        },
        "crypto.price": {
            "name": "crypto.price",
            "description": "Get cryptocurrency price",
            "parameters": {
                "symbol": {"type": "string", "description": "Crypto symbol like BTC, ETH", "required": True},
                "currency": {"type": "string", "description": "Target currency like USD, KZT", "required": False}
            },
            "mock_response": {
                "symbol": "",
                "price": None,
                "currency": "",
                "change_24h": ""
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
            },
            "mock_response": {
                "items": [
                    {
                        "id": "", 
                        "name": "", 
                        "price": None, 
                        "currency": "", 
                        "in_stock": None
                    }
                ]
            }
        },
        "shop.add_to_cart": {
            "name": "shop.add_to_cart",
            "description": "Add product to shopping cart",
            "parameters": {
                "productId": {"type": "string", "description": "Product ID", "required": True},
                "quantity": {"type": "int", "description": "Number of items", "required": False}
            },
            "mock_response": {
                "cart_id": "",
                "status": "",
                "total_items": None,
                "total_price": None
            }
        },
        "shop.checkout": {
            "name": "shop.checkout",
            "description": "Complete purchase",
            "parameters": {
                "cartId": {"type": "string", "description": "Shopping cart ID", "required": True},
                "paymentMethod": {"type": "string", "description": "card, cash, bank_transfer", "required": True}
            },
            "mock_response": {
                "order_id": "",
                "status": "",
                "delivery_estimate": ""
            }
        },
        # === ДОКУМЕНТАЦИЯ ===
        "docs.retrieve": {
            "name": "docs.retrieve",
            "description": "Get API documentation for a service",
            "parameters": {
                "service": {"type": "string", "description": "Service name", "required": True},
                "function": {"type": "string", "description": "Function name", "required": True}
            },
            "mock_response": {
                "parameters": {

                },
                "required": []
            }
        },
        # === АНАЛИЗ ТЕКСТА ===
        "nlp.sentiment": {
            "name": "nlp.sentiment",
            "description": "Analyze sentiment of text",
            "parameters": {
                "text": {"type": "string", "description": "Text to analyze", "required": True},
                "language": {"type": "string", "description": "Language code", "required": False}
            },
            "mock_response": {
                "sentiment": "",
                "score": None,
                "language": ""
            }
        },
        "nlp.translate": {
            "name": "nlp.translate",
            "description": "Translate text between languages",
            "parameters": {
                "text": {"type": "string", "description": "Text to translate", "required": True},
                "from_lang": {"type": "string", "description": "Source language", "required": True},
                "to_lang": {"type": "string", "description": "Target language", "required": True}
            },
            "mock_response": {
                "original": "",
                "translated": "",
                "from": "",
                "to": ""
            }
        },
        # === СЕТЬ И СИСТЕМА ===
        "network.speedtest": {
            "name": "network.speedtest",
            "description": "Test internet connection speed",
            "parameters": {
                "server": {"type": "string", "description": "Test server location", "required": False}
            },
            "mock_response": {
                "download_mbps": None,
                "upload_mbps": None,
                "ping_ms": None,
                "server": ""
            }
        },
        "system.time": {
            "name": "system.time",
            "description": "Get current time in timezone",
            "parameters": {
                "timezone": {"type": "string", "description": "Timezone like Asia/Almaty", "required": True}
            },
            "mock_response": {
                "timezone": "",
                "iso_time": "",
                "day_of_week": ""
            }
        },
        # === МЕДИА ===
        "images.search": {
            "name": "images.search",
            "description": "Search for images",
            "parameters": {
                "query": {"type": "string", "description": "Image search query", "required": True},
                "limit": {"type": "int", "description": "Number of results", "required": False}
            },
            "mock_response": {
                "images": [
                    {
                        "url": "", 
                        "caption": "", 
                        "width": None, 
                        "height": None
                    }
                ]
            }
        },
        "video.search": {
            "name": "video.search",
            "description": "Search for videos",
            "parameters": {
                "query": {"type": "string", "description": "Video search query", "required": True},
                "platform": {"type": "string", "description": "youtube, vimeo, all", "required": False}
            },
            "mock_response": {
                "videos": [
                    {
                        "title": "", 
                        "url": "", 
                        "duration": "", 
                        "views": None
                    }
                ]
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
            },
            "mock_response": {
                "events": [
                    {
                        "id": "", 
                        "name": "", 
                        "venue": "", 
                        "date": "", 
                        "tickets_available": None
                    }
                ]
            }
        },
        "tickets.book": {
            "name": "tickets.book",
            "description": "Book event tickets",
            "parameters": {
                "eventId": {"type": "string", "description": "Event ID from search", "required": True},
                "quantity": {"type": "int", "description": "Number of tickets", "required": True},
                "seatType": {"type": "string", "description": "vip, regular, balcony", "required": False}
            },
            "mock_response": {
                "booking_ref": "",
                "event": "",
                "seats": [],
                "total_price": None
            }
        },
        "restaurant.search": {
            "name": "restaurant.search",
            "description": "Search restaurants",
            "parameters": {
                "city": {"type": "string", "description": "City name", "required": True},
                "cuisine": {"type": "string", "description": "Cuisine type", "required": False},
                "priceRange": {"type": "string", "description": "budget, mid, expensive", "required": False}
            },
            "mock_response": {
                "restaurants": [
                    {
                        "id": "", 
                        "name": "", 
                        "cuisine": "", 
                        "rating": None, 
                        "address": ""
                    }
                ]
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
            },
            "mock_response": {
                "reservation_id": "",
                "status": "",
                "restaurant": "",
                "time": ""
            }
        }
    }

# --- ВАЛИДАЦИЯ ---
def validate_entry(tool_name, args_json, out_json, tool_lib):
    errors = []
    try:
        args = json.loads(args_json)
        output = json.loads(out_json)
        if tool_name in tool_lib:
            schema = tool_lib[tool_name]['parameters']
            for param, details in schema.items():
                if details.get('required') and (param not in args or args[param] == ""):
                    errors.append(f"Инструмент '{tool_name}': пропущен '{param}'")
        
        def check_null(obj, path="root"):
            if isinstance(obj, dict):
                for k, v in obj.items(): check_null(v, f"{path}.{k}")
            elif obj is None: errors.append(f"Ошибка null в '{path}'")
        check_null(output)
    except: return ["Ошибка формата JSON"]
    return errors

def update_tool_template(step_id):
    tool_key = f"tool_select_{step_id}"
    selected_tool = st.session_state.get(tool_key)
    lib = get_tool_library()
    
    if selected_tool and selected_tool in lib:
        st.session_state[f"args_{step_id}"] = json.dumps(
            {k: "" for k in lib[selected_tool]['parameters']}, 
            indent=2, ensure_ascii=False
        )
        st.session_state[f"is_err_{step_id}"] = False 
        st.session_state[f"output_{step_id}"] = json.dumps(
            lib[selected_tool].get('mock_response', {}), 
            indent=2, ensure_ascii=False
        )

def toggle_error_state(step_id):
    is_error = st.session_state.get(f"is_err_{step_id}", False)
    tool_key = f"tool_select_{step_id}"
    selected_tool = st.session_state.get(tool_key)
    lib = get_tool_library()
    
    if is_error:
        error_template = {
            "error": True, "type": "InternalServerError",
            "message": "External service is unavailable", "code": 500
        }
        st.session_state[f"output_{step_id}"] = json.dumps(error_template, indent=2, ensure_ascii=False)
    elif selected_tool and selected_tool in lib:
        st.session_state[f"output_{step_id}"] = json.dumps(
            lib[selected_tool].get('mock_response', {}), 
            indent=2, ensure_ascii=False
        )

# --- АВТОРИЗАЦИЯ ---
if not st.session_state['logged_in']:
    st.title("🔐 Вход")
    u = st.text_input("Логин")
    p = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        with sqlite3.connect(DB_FILE) as conn:
            res = conn.execute('SELECT password FROM users WHERE username = ?', (u,)).fetchone()
            if res and make_hashes(p) == res[0]:
                st.session_state.update({'logged_in': True, 'username': u})
                st.rerun()
            else: st.error("Ошибка")
    st.stop()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
# Добавлен пункт "Редактирование"
page = st.sidebar.radio("Навигация", ["Аннотация", "Редактирование", "Экспорт"])
if st.sidebar.button("Выйти"):
    st.session_state['logged_in'] = False
    st.rerun()

# ==========================================
# 1. СТРАНИЦА: АННОТАЦИЯ
# ==========================================
if page == "Аннотация":
    if st.session_state.get('need_reset'):
        for key in list(st.session_state.keys()):
            if any(key.startswith(p) for p in ("plan_", "thought_", "tool_select_", "args_", "output_", "prev_tool_")):
                if "tool_select" in key: st.session_state[key] = "(Нет вызова)"
                elif "args" in key or "output" in key: st.session_state[key] = "{}"
                else: st.session_state[key] = ""
        st.session_state.update({
            'user_query': "", 'selected_tools': [], 'final_answer': "",
            'tool_steps': [{"id": 0}], 'step_counter': 1, 'need_reset': False
        })
        st.rerun()

    st.header("📝 Аннотирование")
    
    col_m1, col_m2, col_m3 = st.columns([2, 1, 2])
    cat_list = ["01_tool_awareness_abstention", "02_tool_selection_disambiguation", "03_planning_multistep_composition", "04_api_discovery_retrieval", "05_argument_schema_mapping", "06_state_session_context", "07_tool_output_interpretation", "08_exception_failure_handling", "09_final_answer_synthesis", "10_multilingual_locale_fidelity"]
    category = col_m1.selectbox("Категория", cat_list, key="current_category")
    difficulty = col_m2.selectbox("Сложность", ["easy", "hard"])
    
    if 'cur_id' not in st.session_state or st.session_state.get('last_cat') != category:
        st.session_state['cur_id'] = f"kk_{category}_{datetime.now().strftime('%m%d_%H%M')}"
        st.session_state['last_cat'] = category
    sample_id = col_m3.text_input("ID образца", value=st.session_state['cur_id'])

    query = st.text_area("Запрос пользователя (на казахском)", key="user_query", height=80)
    lib = get_tool_library()
    sel_tools = st.multiselect("Доступные инструменты", list(lib.keys()), key="selected_tools")

    st.subheader("⚙️ Процесс решения")

    def add_step_callback():
        st.session_state['tool_steps'].append({"id": st.session_state['step_counter']})
        st.session_state['step_counter'] += 1

    def remove_step_callback():
        if len(st.session_state['tool_steps']) > 1:
            st.session_state['tool_steps'].pop()

    c_add, c_rem = st.columns([1, 8])
    c_add.button("➕ Добавить шаг", on_click=add_step_callback)
    c_rem.button("➖ Удалить шаг", on_click=remove_step_callback)

    steps_data = []
    global_errors = []

    for i, step in enumerate(st.session_state['tool_steps']):
        with st.container(border=True):
            st.caption(f"ШАГ {i+1}")
            cp, ct, cs = st.columns(3)
            
            s_plan = cp.text_input("Assistant Plan(Meta на англ)", key=f"plan_{step['id']}")
            s_thought = ct.text_input("Мысль ассистента(на казахском)", key=f"thought_{step['id']}")
            
            s_tool = cs.selectbox("Инструмент", ["(Нет вызова)"] + sel_tools, key=f"tool_select_{step['id']}", on_change=update_tool_template, kwargs={"step_id": step['id']})
            if s_tool != "(Нет вызова)":
                cs.checkbox("⚠️ Симуляция ошибки API", key=f"is_err_{step['id']}", on_change=toggle_error_state, kwargs={"step_id": step['id']})

            if f"args_{step['id']}" not in st.session_state: st.session_state[f"args_{step['id']}"] = "{}"
            if f"output_{step['id']}" not in st.session_state: st.session_state[f"output_{step['id']}"] = "{}"

            ca, co = st.columns(2)
            s_args = ca.text_area("Arguments (JSON)", key=f"args_{step['id']}", height=120)
            s_out = co.text_area("Output (JSON)", key=f"output_{step['id']}", height=120)

            if s_tool != "(Нет вызова)":
                errs = validate_entry(s_tool, s_args, s_out, lib)
                for e in errs: st.error(e)
                global_errors.extend(errs)
            
            steps_data.append({"tool": s_tool, "args": s_args, "output": s_out, "plan": s_plan, "thought": s_thought})

    final = st.text_area("Итоговый ответ", key="final_answer")

    if st.button("💾 СОХРАНИТЬ В БД", type="primary", use_container_width=True):
        if global_errors or not query or not final:
            st.error("Ошибка! Проверьте JSON и заполните все поля.")
        elif sample_id in get_existing_ids():
            st.error("Этот ID уже существует!")
        else:
            turns = [{"role": "user", "content": query}]
            ans_list = []
            for s in steps_data:
                if s['plan'] or s['thought']:
                    turns.append({"role": "assistant", "content": s['thought'], "meta": {"plan": s['plan']}})
                if s['tool'] != "(Нет вызова)":
                    a_o = json.loads(s['args'])
                    turns.append({"role": "assistant", "tool_call": {"name": s['tool'], "arguments": a_o}})
                    turns.append({"role": "tool", "content": s['output']})
                    ans_list.append({"name": s['tool'], "arguments": a_o})
            turns.append({"role": "assistant", "content": final})

            with sqlite3.connect(DB_FILE) as conn:
                conn.execute('INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?,?)', 
                             (sample_id, category, difficulty, query, 
                              json.dumps([lib[n] for n in sel_tools if n in lib], ensure_ascii=False),
                              json.dumps(ans_list, ensure_ascii=False),
                              json.dumps(turns, ensure_ascii=False),
                              st.session_state['username'], datetime.now()))
            
            st.success("Данные успешно сохранены!")
            st.session_state['need_reset'] = True
            st.cache_data.clear()
            st.rerun()

# ==========================================
# 2. СТРАНИЦА: РЕДАКТИРОВАНИЕ (НОВОЕ)
# ==========================================
elif page == "Редактирование":
    st.header("✏️ Редактирование записей")
    
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT id, category, created_at FROM annotations ORDER BY created_at DESC", conn)
        
    if df.empty:
        st.info("В базе данных пока нет записей для редактирования.")
    else:
        # Выбор записи
        options = df['id'].tolist()
        selected_edit_id = st.selectbox("Выберите ID записи для исправления", options)
        
        # Кнопка загрузки парсит сохраненный JSON и восстанавливает шаги
        if st.button("🔄 Загрузить данные в редактор"):
            with sqlite3.connect(DB_FILE) as conn:
                rec = conn.execute("SELECT * FROM annotations WHERE id = ?", (selected_edit_id,)).fetchone()
            
            turns = json.loads(rec[6]) # turns_json
            tools_loaded = [t['name'] for t in json.loads(rec[4])] # Выбранные тулы
            
            st.session_state['edit_loaded_id'] = selected_edit_id
            st.session_state['e_query'] = rec[3]
            st.session_state['e_cat'] = rec[1]
            st.session_state['e_diff'] = rec[2]
            st.session_state['e_sel_tools'] = tools_loaded
            st.session_state['e_final'] = turns[-1]['content'] if turns and turns[-1]['role'] == 'assistant' and 'tool_call' not in turns[-1] else ""
            
            # Логика восстановления шагов из списка Turns
            middle_turns = turns[1:-1] if len(turns) > 2 else []
            if not middle_turns and len(turns) == 2 and 'tool_call' not in turns[1]: 
                middle_turns = []
                
            steps = []
            cur = {"plan": "", "thought": "", "tool": "(Нет вызова)", "args": "{}", "output": "{}"}
            
            for t in middle_turns:
                if t["role"] == "assistant" and "content" in t and "tool_call" not in t:
                    # Если уже есть заполненный тул или мысль, закрываем шаг
                    if cur["thought"] or cur["tool"] != "(Нет вызова)":
                        steps.append(cur)
                        cur = {"plan": "", "thought": "", "tool": "(Нет вызова)", "args": "{}", "output": "{}"}
                    cur["thought"] = t.get("content", "")
                    cur["plan"] = t.get("meta", {}).get("plan", "")
                elif t["role"] == "assistant" and "tool_call" in t:
                    cur["tool"] = t["tool_call"]["name"]
                    cur["args"] = json.dumps(t["tool_call"]["arguments"], indent=2, ensure_ascii=False)
                elif t["role"] == "tool":
                    cur["output"] = t.get("content", "{}")
                    steps.append(cur)
                    cur = {"plan": "", "thought": "", "tool": "(Нет вызова)", "args": "{}", "output": "{}"}
                    
            # Добавление незаконченного шага (если цикл кончился на Thought)
            # if any(v for k,v in cur.items() if k not in ['args', 'output'] and v) or cur["tool"] != "(Нет вызова)":
            #     steps.append(cur)
            if cur["plan"] or cur["thought"] or cur["tool"] != "(Нет вызова)":
                steps.append(cur)
                
            if not steps: 
                steps = [{"plan": "", "thought": "", "tool": "(Нет вызова)", "args": "{}", "output": "{}"}]
            
            st.session_state['edit_tool_steps'] = [{"id": f"e{i}"} for i in range(len(steps))]
            st.session_state['edit_step_counter'] = len(steps)
            
            # Заполняем Session State для отрисовки полей
            for i, s_data in enumerate(steps):
                sid = f"e{i}"
                st.session_state[f"plan_{sid}"] = s_data["plan"]
                st.session_state[f"thought_{sid}"] = s_data["thought"]
                st.session_state[f"tool_select_{sid}"] = s_data["tool"]
                st.session_state[f"args_{sid}"] = s_data["args"]
                st.session_state[f"output_{sid}"] = s_data["output"]
                st.session_state[f"is_err_{sid}"] = False
            
            st.rerun()

        # --- ОТРИСОВКА ФОРМЫ РЕДАКТИРОВАНИЯ ---
        if st.session_state.get('edit_loaded_id') == selected_edit_id:
            st.divider()
            
            col_m1, col_m2 = st.columns(2)
            cat_list = ["01_tool_awareness_abstention", "02_tool_selection_disambiguation", "03_planning_multistep_composition", "04_api_discovery_retrieval", "05_argument_schema_mapping", "06_state_session_context", "07_tool_output_interpretation", "08_exception_failure_handling", "09_final_answer_synthesis", "10_multilingual_locale_fidelity"]
            
            try: cat_idx = cat_list.index(st.session_state['e_cat'])
            except: cat_idx = 0
            e_cat = col_m1.selectbox("Категория", cat_list, index=cat_idx)
            
            diff_list = ["easy", "hard"]
            try: diff_idx = diff_list.index(st.session_state['e_diff'])
            except: diff_idx = 0
            e_diff = col_m2.selectbox("Сложность", diff_list, index=diff_idx)
            
            e_query = st.text_area("Запрос пользователя", value=st.session_state.get('e_query', ''), height=80)
            
            lib = get_tool_library()
            e_sel_tools = st.multiselect("Доступные инструменты", list(lib.keys()), default=st.session_state.get('e_sel_tools', []))
            
            st.subheader("⚙️ Процесс решения (Редактирование)")
            
            def edit_add_step():
                new_id = f"e{st.session_state['edit_step_counter']}"
                st.session_state['edit_tool_steps'].append({"id": new_id})
                st.session_state['edit_step_counter'] += 1

            def edit_rem_step():
                if len(st.session_state['edit_tool_steps']) > 1:
                    st.session_state['edit_tool_steps'].pop()

            c_add, c_rem = st.columns([1, 8])
            c_add.button("➕ Добавить шаг", on_click=edit_add_step, key="btn_e_add")
            c_rem.button("➖ Удалить шаг", on_click=edit_rem_step, key="btn_e_rem")
            
            edit_steps_data = []
            e_global_errors = []
            
            for i, step in enumerate(st.session_state['edit_tool_steps']):
                sid = step['id']
                with st.container(border=True):
                    st.caption(f"ШАГ {i+1}")
                    cp, ct, cs = st.columns(3)
                    
                    e_plan = cp.text_input("Assistant Plan", value=st.session_state.get(f"plan_{sid}", ""), key=f"plan_{sid}")
                    e_thought = ct.text_input("Мысль ассистента", value=st.session_state.get(f"thought_{sid}", ""), key=f"thought_{sid}")
                    
                    tool_val = st.session_state.get(f"tool_select_{sid}", "(Нет вызова)")
                    try: tool_idx = (["(Нет вызова)"] + e_sel_tools).index(tool_val)
                    except: tool_idx = 0
                    
                    e_tool = cs.selectbox("Инструмент", ["(Нет вызова)"] + e_sel_tools, index=tool_idx, key=f"tool_select_{sid}", on_change=update_tool_template, kwargs={"step_id": sid})
                    
                    if e_tool != "(Нет вызова)":
                        cs.checkbox("⚠️ Симуляция ошибки API", value=st.session_state.get(f"is_err_{sid}", False), key=f"is_err_{sid}", on_change=toggle_error_state, kwargs={"step_id": sid})
                    
                    ca, co = st.columns(2)
                    e_args = ca.text_area("Arguments (JSON)", value=st.session_state.get(f"args_{sid}", "{}"), key=f"args_{sid}", height=120)
                    e_out = co.text_area("Output (JSON)", value=st.session_state.get(f"output_{sid}", "{}"), key=f"output_{sid}", height=120)
                    
                    if e_tool != "(Нет вызова)":
                        errs = validate_entry(e_tool, e_args, e_out, lib)
                        for e in errs: st.error(e)
                        e_global_errors.extend(errs)
                        
                    edit_steps_data.append({"tool": e_tool, "args": e_args, "output": e_out, "plan": e_plan, "thought": e_thought})
                    
            e_final = st.text_area("Итоговый ответ", value=st.session_state.get('e_final', ''), key="e_final_text")
            
            if st.button("💾 ОБНОВИТЬ В БД", type="primary", use_container_width=True):
                if e_global_errors or not e_query or not e_final:
                    st.error("Ошибка! Проверьте JSON и заполните все поля.")
                else:
                    turns = [{"role": "user", "content": e_query}]
                    ans_list = []
                    for s in edit_steps_data:
                        if s['plan'] or s['thought']:
                            turns.append({"role": "assistant", "content": s['thought'], "meta": {"plan": s['plan']}})
                        if s['tool'] != "(Нет вызова)":
                            a_o = json.loads(s['args'])
                            turns.append({"role": "assistant", "tool_call": {"name": s['tool'], "arguments": a_o}})
                            turns.append({"role": "tool", "content": s['output']})
                            ans_list.append({"name": s['tool'], "arguments": a_o})
                    turns.append({"role": "assistant", "content": e_final})

                    with sqlite3.connect(DB_FILE) as conn:
                        conn.execute('''
                            UPDATE annotations 
                            SET category=?, difficulty=?, query=?, tools_json=?, answers_json=?, turns_json=?
                            WHERE id=?
                        ''', (e_cat, e_diff, e_query, 
                              json.dumps([lib[n] for n in e_sel_tools if n in lib], ensure_ascii=False),
                              json.dumps(ans_list, ensure_ascii=False),
                              json.dumps(turns, ensure_ascii=False),
                              selected_edit_id))
                    
                    st.success("✅ Запись успешно обновлена!")
                    st.session_state.pop('edit_loaded_id', None)
                    st.cache_data.clear()

# ==========================================
# 3. СТРАНИЦА: ЭКСПОРТ
# ==========================================
elif page == "Экспорт":
    st.header("📊 Статистика")
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT * FROM annotations", conn)

    if df.empty:
        st.info("Данных пока нет.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Распределение по категориям**")
            st.bar_chart(df['category'].value_counts())
        with c2:
            st.write("**Статистика по сложности**")
            diff_stats = df['difficulty'].value_counts().reset_index()
            diff_stats.columns = ['Сложность', 'Кол-во']
            diff_stats['Процент'] = (diff_stats['Кол-во'] / diff_stats['Кол-во'].sum() * 100).round(1).astype(str) + '%'
            st.table(diff_stats)

        st.divider()
        st.subheader("Выгрузка")
        scat = st.selectbox("Выберите категорию для скачивания", df['category'].unique())
        if st.button("Сгенерировать файл"):
            subset = df[df['category'] == scat]
            export_data = []
            for _, r in subset.iterrows():
                export_data.append({
                    "id": r['id'], "query": r['query'], "category": r['category'],
                    "tools": json.loads(r['tools_json']), "turns": json.loads(r['turns_json'])
                })
            st.download_button("⬇️ Скачать JSON", json.dumps(export_data, indent=2, ensure_ascii=False), f"{scat}.json")
