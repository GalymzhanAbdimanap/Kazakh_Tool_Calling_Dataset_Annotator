import streamlit as st
import sqlite3
import json
import uuid
from datetime import datetime
import pandas as pd

# --- КОНФИГУРАЦИЯ И БАЗА ДАННЫХ ---
DB_FILE = "kazakh_tool_dataset.db"

def init_db():
    """Инициализация SQLite базы данных с нужной схемой."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Создаем таблицу, соответствующую полям из PDF [cite: 41-53]
    c.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id TEXT PRIMARY KEY,
            category TEXT,
            difficulty TEXT,
            query TEXT,
            tools_json TEXT,  -- Храним как JSON строку для удобства, при экспорте строкифицируем
            answers_json TEXT, -- Храним как JSON строку
            turns_json TEXT,   -- Полный диалог
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO annotations 
        (id, category, difficulty, query, tools_json, answers_json, turns_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['id'], data['category'], data['difficulty'], data['query'],
        json.dumps(data['tools'], ensure_ascii=False),
        json.dumps(data['answers'], ensure_ascii=False),
        json.dumps(data['turns'], ensure_ascii=False)
    ))
    conn.commit()
    conn.close()

# --- БИБЛИОТЕКА ИНСТРУМЕНТОВ (ИЗ PDF [cite: 102-229]) ---
def get_tool_library():
    """Возвращает словарь доступных инструментов согласно PDF."""
    return {
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
        "flights.search": {
            "name": "flights.search",
            "description": "Search available flights between airports",
            "parameters": {
                "from": {"type": "string", "description": "Departure airport code", "required": True},
                "to": {"type": "string", "description": "Arrival airport code", "required": True},
                "date": {"type": "string", "description": "Departure date YYYY-MM-DD", "required": True}
            }
        },
         "flights.book": {
            "name": "flights.book",
            "description": "Book a specific flight",
            "parameters": {
                "flightId": {"type": "string", "description": "Flight ID from search", "required": True},
                "passengerName": {"type": "string", "description": "Passenger full name", "required": True}
            }
        },
        "calendar.add": {
            "name": "calendar.add",
            "description": "Add new calendar event",
            "parameters": {
                "title": {"type": "string", "description": "Event title", "required": True},
                "datetime": {"type": "string", "description": "Start time RFC3339", "required": True}
            }
        },
        # Добавьте остальные инструменты из PDF при необходимости
    }

# --- UI ИНТЕРФЕЙС ---
st.set_page_config(page_title="Kazakh Tool-Call Annotator", layout="wide")
init_db()

st.title("🇰🇿 Kazakh Tool-Calling Dataset Annotator")
st.markdown("Инструмент для создания датасета согласно методологии APIGen[cite: 1].")

# Сайдбар для навигации
page = st.sidebar.radio("Меню", ["Аннотация (Добавить данные)", "Экспорт (Скачать JSON)"])

# === СТРАНИЦА АННОТАЦИИ ===
if page == "Аннотация (Добавить данные)":
    st.header("Новая запись")

    # 1. Метаданные [cite: 42-45]
    col1, col2 = st.columns(2)
    with col1:
        # Категории из PDF [cite: 33-39]
        category = st.selectbox("Категория (Category)", [
            "tool_awareness_abstention",
            "tool_selection_disambiguation",
            "planning_multistep_composition",
            "api_discovery_retrieval",
            "argument_schema_mapping",
            "state_session_context",
            "tool_output_interpretation",
            "exception_failure_handling",
            "final_answer_synthesis",
            "multilingual_locale_fidelity"
        ])
    with col2:
        difficulty = st.selectbox("Сложность (Difficulty)", ["easy", "hard"])

    # Генерация ID (можно заменить на ручной ввод, если нужно строго по порядку)
    sample_id = st.text_input("ID образца", value=f"kk_{category}_001")

    # 2. Пользовательский запрос [cite: 46]
    query = st.text_area("Запрос пользователя (на казахском)", 
                         placeholder="Астанада қазір ауа райы қандай?",
                         help="Используйте культурный контекст: города КЗ, тенге, местные имена.")

    # 3. Выбор инструментов (Dropdown) [cite: 47]
    st.subheader("🛠 Выбор инструментов")
    tool_lib = get_tool_library()
    selected_tool_names = st.multiselect("Выберите доступные инструменты для этого диалога", 
                                         options=list(tool_lib.keys()))
    
    # Формируем список объектов инструментов автоматически
    selected_tools_objs = [tool_lib[name] for name in selected_tool_names]
    st.json(selected_tools_objs, expanded=False)

    # 4. Построение диалога (Turns) [cite: 48-51]
    st.subheader("💬 Диалог (Turns)")
    st.info("Заполните шаги диалога.")

    # Шаг 1: Мысли и План (Assistant Turn)
    st.markdown("**Шаг 1: Мысли ассистента**")
    col_t1, col_t2 = st.columns(2)
    
    with col_t1:
        # План на английском (Meta)
        plan = st.text_input("Assistant Plan (Meta, на английском)", 
                             placeholder="Use geocode service for coordinates")
    
    with col_t2:
        # Текстовое пояснение действий на казахском (Content)
        assistant_thought = st.text_input(
            "Пояснение перед вызовом (на казахском)", 
            placeholder="Координаталар үшін геокодтау қызметін пайдаланамын.",
            help="Это текст, который ассистент говорит пользователю перед использованием инструмента."
        )

    # Шаг 2: Вызов инструмента (Tool Call)
    st.markdown("**Шаг 2: Вызов инструмента (Tool Call)**")
    
    # Используем key, чтобы сбрасывать состояние при смене инструмента (опционально)
    call_tool_name = st.selectbox("Какой инструмент вызвать?", ["(Нет вызова)"] + selected_tool_names)
    
    call_args = "{}"
    
    if call_tool_name != "(Нет вызова)":
        # 1. Находим определение выбранного инструмента в библиотеке
        current_tool_def = tool_lib[call_tool_name]
        
        # 2. Извлекаем параметры (схема)
        # Пример структуры в PDF: "parameters": { "city": {"type": "string"...}, ... } [cite: 108-110]
        params_schema = current_tool_def.get("parameters", {})
        
        # 3. Генерируем шаблон (Template) для удобного заполнения
        # Ключи берем реальные, а значения — как подсказки
        arg_template = {}
        for param_name, param_details in params_schema.items():
            p_type = param_details.get("type", "string")
            # Если параметр обязательный, помечаем это
            is_req = " (обязательно)" if param_details.get("required") else ""
            arg_template[param_name] = f"<{p_type}>{is_req}"
        
        # Превращаем шаблон в красивую строку JSON
        default_json_val = json.dumps(arg_template, indent=4, ensure_ascii=False)

        # 4. Отображаем поле ввода с предзаполненным шаблоном
        # ВАЖНО: key=f"args_{call_tool_name}" заставляет Streamlit обновлять поле при смене инструмента
        call_args = st.text_area(
            "Аргументы (JSON)", 
            value=default_json_val, 
            height=250,
            key=f"args_{call_tool_name}", 
            help="Замените значения в <...> на реальные данные из контекста."
        )
        
        # Дополнительно: Показываем полное описание параметров (Read-only) для справки
        with st.expander(f"ℹ️ Справка по параметрам {call_tool_name}"):
            st.json(params_schema)

    # Шаг 3: Ответ инструмента (Tool Output)
    tool_output = ""
    if call_tool_name != "(Нет вызова)":
        st.markdown("**Шаг 3: Ответ API (Tool Output)**")
        tool_output = st.text_area("Результат от инструмента (Raw JSON)", 
                                   value='{"temperature": -12, "description": "snow"}',
                                   help="Реалистичный ответ от API")

    # Шаг 4: Финальный ответ
    st.markdown("**Шаг 4: Итоговый ответ**")
    final_answer = st.text_area("Финальный ответ (на казахском)", 
                                placeholder="Астанада қазір -12°C. (Дерек көзі: weather.get)")

    # Кнопка сохранения
    if st.button("Сохранить в БД"):
        if not query:
            st.error("Введите запрос пользователя!")
        else:
            # Сборка структуры Turns согласно схеме PDF
            turns = []
            
            # 1. User Turn
            turns.append({"role": "user", "content": query})
            
            # 2. Assistant Turn (Plan + Thought + Tool Call)
            if call_tool_name != "(Нет вызова)":
                try:
                    args_json = json.loads(call_args)
                    
                    # Формируем объект ассистента
                    # Если поле ввода пустое, ставим дефолтное значение, иначе берем введенное
                    content_text = assistant_thought if assistant_thought else "Ақпаратты тексеремін."
                    
                    turns.append({
                        "role": "assistant", 
                        "content": content_text,  # <-- Теперь здесь ваш текст из инпута
                        "meta": {"plan": plan},
                        "tool_call": {
                            "name": call_tool_name,
                            "arguments": args_json
                        }
                    })
                    
                    # 3. Tool Output
                    turns.append({
                        "role": "tool",
                        "content": tool_output
                    })
                except json.JSONDecodeError:
                    st.error("Ошибка JSON в аргументах!")
                    st.stop()
            else:
                # Если инструменты не нужны (категория Tool Awareness - Abstention) [cite: 235]
                # Просто добавляем ответ ассистента без tool_call
                pass

            # 4. Final Answer
            turns.append({"role": "assistant", "content": final_answer})

            # Сборка answers (expected calls)
            answers = []
            if call_tool_name != "(Нет вызова)":
                answers.append({"name": call_tool_name, "arguments": json.loads(call_args)})

            # Формирование полного объекта
            data_obj = {
                "id": sample_id,
                "category": category,
                "difficulty": difficulty,
                "query": query,
                "tools": selected_tools_objs,
                "answers": answers,
                "turns": turns
            }
            
            save_to_db(data_obj)
            st.success(f"Запись {sample_id} успешно сохранена!")

# === СТРАНИЦА ЭКСПОРТА ===
elif page == "Экспорт (Скачать JSON)":
    st.header("Экспорт данных")
    
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM annotations", conn)
    conn.close()

    st.dataframe(df)

    # Фильтр по категории для скачивания
    categories = df['category'].unique().tolist()
    selected_cat = st.selectbox("Выберите категорию для скачивания", categories)

    if st.button("Сгенерировать JSON файл"):
        subset = df[df['category'] == selected_cat]
        
        final_json_list = []
        
        for index, row in subset.iterrows():
            # Важный момент из PDF: поля tools и answers должны быть STRINGIFIED JSON 
            # В БД мы храним их как JSON-строку, но Python json.dumps заэкранирует её еще раз, 
            # что и требуется (строка внутри JSON).
            
            # Парсим из БД, чтобы убедиться в структуре
            tools_obj = json.loads(row['tools_json'])
            answers_obj = json.loads(row['answers_json'])
            turns_obj = json.loads(row['turns_json'])

            # Собираем финальный объект
            item = {
                "id": row['id'],
                "category": row['category'],
                "difficulty": row['difficulty'],
                "query": row['query'],
                "tools": json.dumps(tools_obj, ensure_ascii=False),     # <-- Строкификация списка инструментов
                "answers": json.dumps(answers_obj, ensure_ascii=False), # <-- Строкификация списка ответов
                "turns": turns_obj                                      # <-- Обычный массив
            }
            final_json_list.append(item)

        # Конвертация в JSON
        json_str = json.dumps(final_json_list, indent=2, ensure_ascii=False)
        
        # Имя файла согласно инструкции 
        file_name_map = {
            "tool_awareness_abstention": "01_tool_awareness_abstention.json",
            "tool_selection_disambiguation": "02_tool_selection_disambiguation.json",
            "planning_multistep_composition": "03_planning_multistep_composition.json"
            # и так далее...
        }
        fname = file_name_map.get(selected_cat, f"{selected_cat}.json")

        st.download_button(
            label=f"Скачать {fname}",
            data=json_str,
            file_name=fname,
            mime="application/json"
        )
        st.success(f"Готово к скачиванию! Файл отформатирован согласно требованиям PDF.")
