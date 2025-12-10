![CI](https://github.com/nondeletable/URL-Cutter/actions/workflows/ci.yml/badge.svg)

# URL Cutter

A convenient desktop application for shortening long URLs, built with Python and Flet.

---

## 🚀 Features

- Input a long URL and instantly get a shortened version.
- Uses `pyshorteners` (TinyURL) as the shortening backend.
- Copy shortened links directly to the clipboard.
- Clear input fields with a single click.
- **New in v1.2.4:**
  - History window with table view of shortened links.
  - Search and filtering by URL, service, or date.
  - Customizable table columns.
- Responsive and minimalist interface.

---

## 🛠 Technologies

- Python
- Flet (for GUI)
- pyshorteners (for URL shortening)
- SQLAlchemy + Alembic (for history storage and migrations)

---

## ⚙️ How to Run

1. Clone the repository:

```bash
git clone https://github.com/nondeletable/URL-Cutter.git
cd URL-Cutter
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python lite_upgrade.py
```
---

## 📸 Screenshots

Main window

![Main window](urlcutter/assets/screenshots/main%20window.jpg)

Dropdown menu

![Dropdown menu](urlcutter/assets/screenshots/dropdown%20menu.jpg)

History window

![History window](urlcutter/assets/screenshots/history.jpg)

---

## Download

Download the latest Windows build (.exe) from [Releases](https://github.com/nondeletable/URL-Cutter/releases) page.

---

## 📫 Contacts

* **Telegram:** [@nondeletable](https://t.me/nondeletable)
* **Email:** [nondeletable@gmail.com](mailto:nondeletable@gmail.com)

✨ Thank you for using URL Cutter! We hope it makes your workflow faster and easier.
