# UrlCutter — История ссылок (Contracts / Specs)
Версия: 0.1 (draft)
Статус: согласовано на UX/архитектурном уровне, без реализации

## 0. Контекст и цели
Модуль «История ссылок» фиксирует результаты сокращения, позволяет фильтровать/искать, просматривать и экспортировать записи.
Хранилище: SQLite (user data dir), ORM: SQLAlchemy, миграции: Alembic.
UI-вход: кнопка **Menu → История ссылок**.

---

## 1. DTO (структуры данных)

### 1.1. LinkRecord
| Поле            | Тип        | Обяз. | Описание |
|-----------------|------------|-------|----------|
| id              | int        | да    | Уникальный PK записи |
| long_url        | str        | да    | Исходный URL (≤ 2048) |
| short_url       | str        | да    | Короткий URL (≤ 512) |
| service         | str        | да    | Идентификатор сервиса (напр. `"tinyurl"`) |
| created_at_utc  | datetime   | да    | Время создания (UTC) |
| copy_count      | int        | да    | Сколько раз копировали из UI (≥ 0) |

**Инварианты:**
- `long_url`/`short_url` — валидные URL по синтаксису; храним как есть (без нормализации содержимого).
- `copy_count` инкрементируется только по пользовательскому действию «Копировать».

### 1.2. HistoryFilters
| Поле            | Тип                 | Обяз. | Описание |
|-----------------|---------------------|-------|----------|
| query           | str \| null         | нет   | Подстрока, CI; ищем в `long_url` **или** `short_url` |
| date_from_local | date \| null        | нет   | Дата начала (локальная), включительно |
| date_to_local   | date \| null        | нет   | Дата конца (локальная), включительно |
| service         | "ALL" \| str \| null| нет   | Фильтр по сервису; "ALL"/null = без фильтра |

**Валидация:**
- Если заданы обе даты: `date_from_local ≤ date_to_local`.
- Преобразование дат в UTC-интервалы выполняет сервис.

### 1.3. SortSpec
| Поле      | Тип                        | Обяз. | Описание |
|-----------|----------------------------|-------|----------|
| field     | enum                       | да    | `"created_at" \| "service" \| "long_url" \| "short_url" \| "copy_count"` |
| direction | "asc" \| "desc"            | да    | Направление сортировки |

**По умолчанию:** `field="created_at"`, `direction="desc"`.

### 1.4. PageSpec
| Поле      | Тип           | Обяз. | Описание |
|-----------|---------------|-------|----------|
| page      | int           | да    | Страница (1..N), 1-based |
| page_size | int (10/25/50/100) | да | Размер страницы; по умолчанию 50 |

### 1.5. HistoryPage (ответ пагинации)
| Поле      | Тип                | Описание |
|-----------|--------------------|----------|
| items     | list\<LinkRecord>  | Записи текущей страницы |
| total     | int                | Всего записей по фильтрам |
| page      | int                | Текущая страница |
| page_size | int                | Размер страницы |
| has_prev  | bool               | Есть предыдущая |
| has_next  | bool               | Есть следующая |

### 1.6. ExportSpec
| Поле                | Тип             | Обяз. | Описание |
|---------------------|-----------------|-------|----------|
| filters             | HistoryFilters  | да    | Фильтры, влияющие на экспорт |
| sort                | SortSpec        | да    | Порядок строк в CSV |
| locale              | "ru" \| "en"    | да    | Форматирование дат/заголовков (если нужно) |
| filename_suggestion | str             | да    | Предложение имени файла (напр. `urlcutter_history_YYYY-MM-DD.csv`) |

**CSV-правила:** UTF-8, `,` — разделитель, поля с запятыми в кавычках, защита от CSV-инъекций: если значение начинается с `= + - @`, предварять `'`.

---

## 2. Сервис истории (интерфейсы)

### 2.1. Методы
- `list(filters: HistoryFilters, sort: SortSpec, page: PageSpec) -> HistoryPage`
  Возвращает пагинированный список с учётом фильтров/сортировки.

- `add(record: LinkRecord) -> LinkRecord`
  Добавляет запись после успешного сокращения. В `record.id` и `record.created_at_utc` проставляются на стороне сервиса/БД.

- `increment_copy_count(id: int) -> None`
  Увеличивает `copy_count` для записи `id` на 1.

- `delete(id: int) -> None`
  Удаляет запись.

- `export_csv(spec: ExportSpec) -> bytes`
  Возвращает содержимое CSV (байты). Фильтры/сортировка — как в `spec`.

- `distinct_services() -> list[str]`
  Возвращает уникальные `service` из БД (для выпадающего списка), UI добавляет `"ALL"` сам.

### 2.2. Ошибки (общий контракт)
- `ValidationError` — некорректные параметры (напр., `page<1`, неверный `id`).
- `NotFoundError` — запись не найдена/удалена.
- `StorageError` — проблемы с доступом к БД/файлу.
- `ExportError` — ошибка формирования CSV.

---

## 3. UI-контракты (состояния и события)

### 3.1. Состояния экрана History
- `Idle` — таблица загружена, пользователь взаимодействует.
- `Loading` — запрос к сервису в процессе.
- `Empty` — нет данных в выборке (или совсем).
- `Error` — краткое сообщение + кнопка «Повторить».

### 3.2. События UI → Сервис
- `Menu.History.Click`
  Вызов: `list(default_filters, default_sort, default_page)`.

- `Filters.Change(filters)`
  Вызов: `list(filters, current_sort, page=PageSpec(page=1, page_size=current.page_size))`.

- `Sort.Change(sort)`
  Вызов: `list(current_filters, sort, page=current_page_spec)`.

- `Page.Change(page_spec)`
  Вызов: `list(current_filters, current_sort, page_spec)`.

- `Row.Action.Copy(id)`
  Вызовы: `increment_copy_count(id)` → toast `history.toast.copied`.

- `Row.Action.Open(id)`
  Открыть `short_url` в браузере (вне сервиса, UI знает URL из строки).

- `Row.Action.Details(id)`
  Показать модалку с полями `LinkRecord` (без вызова сервиса, данные уже есть в строке).

- `Row.Action.Delete(id)`
  Подтверждение → `delete(id)` → `list(current_filters, current_sort, current_page_spec)`.

- `Toolbar.Export.Click`
  Диалог «Сохранить как…» → `export_csv(ExportSpec)` → сохранить байты.

### 3.3. Отображение
- Дата/время в таблице — локальное (в соответствии с настройкой языка RU/EN). Tooltip — ISO-UTC.
- Длинные URL — усечение с многоточием, tooltip показывает полный URL.
- Поиск — CI, подстрока по обоим полям, debounce ~300–500 мс, Enter применяет сразу.
- Пагинация — «‹ Prev 1 2 3 … Next ›» + селектор: 10/25/50/100 (дефолт 50).
- Сортировка по умолчанию — `Дата ↓` (новые сверху).

---

## 4. I18n (ключи)

menu.history
menu.about
history.title
history.search.placeholder
history.filter.date_from
history.filter.date_to
history.filter.service
history.btn.apply
history.btn.reset
history.btn.export
history.col.date
history.col.service
history.col.long
history.col.short
history.col.copies
history.actions.copy
history.actions.open
history.actions.details
history.actions.delete
history.confirm.delete
history.empty
history.error.load
history.toast.copied

---

## 5. Примеры (JSON-подобные)

### 5.1. Запрос списка (первый вход)
```json
{
  "filters":
      {
        "query": null,
        "date_from_local": null,
        "date_to_local": null,
        "service": "ALL"
      },
  "sort":
      {
        "field": "created_at",
        "direction": "desc"
      },
  "page":
      {
        "page": 1,
        "page_size": 50
      }
}
```

### 5.2. Ответ страницы
```json
{
  "items": [
    {
      "id": 1012,
      "long_url": "https://example.com/articles/how-to-ship",
      "short_url": "https://tinyurl.com/abcd12",
      "service": "tinyurl",
      "created_at_utc": "2025-08-27T01:23:45Z",
      "copy_count": 3
    }
  ],
  "total": 357,
  "page": 1,
  "page_size": 50,
  "has_prev": false,
  "has_next": true
}
```

### 5.3. Экспорт
```json
{
  "filters":
    {
      "query": "ship",
      "date_from_local": "2025-08-01",
      "date_to_local": "2025-08-27",
      "service": "tinyurl"
    },
  "sort":
    {
      "field": "created_at",
      "direction": "desc"
    },
  "locale":  "ru",
  "filename_suggestion": "urlcutter_history_2025-08-27.csv"
}
```

CSV-колонки по умолчанию:
created_at_local,service,long_url,short_url,copy_count
created_at_local форматируется по локали интерфейса (RU/EN).

## 6. Нефункциональные требования

**Производительность**
- Выборка одной страницы ≤ 100 мс при объёме до ~20k записей.
- Индексы по created_at, service; поиск LIKE по префиксу допустим. FTS — опция на будущее.

**Надёжность**
- Первый запуск/пустая БД → состояние Empty без ошибок.
- Ошибки диска/прав → мягкое сообщение в UI и возможность повторить действие.

**Безопасность**
- CSV-инъекции: если значение начинается с =, +, - или @, предварять апострофом '.
- В экспорте только текст; никакой интерпретации URL.

## 7. Точки интеграции

- После успешного сокращения: add(LinkRecord{ long_url, short_url, service, copy_count=0 }).
- Кнопка «Копировать» (главный экран и История): increment_copy_count(id).

## 8. Будущее расширение (не реализуем сейчас)

- Массовое удаление/экспорт выбранных записей.
- Пресеты дат (Сегодня, 7 дней, 30 дней).
- Полнотекстовый поиск (SQLite FTS5).
- Импорт/восстановление истории из CSV.
