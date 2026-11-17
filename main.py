import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "yoma_bot.db")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL, name TEXT NOT NULL,
            description TEXT DEFAULT '', photo_id TEXT DEFAULT '',
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL, title TEXT NOT NULL,
            price REAL NOT NULL, duration TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL, license_key TEXT NOT NULL,
            sold INTEGER DEFAULT 0,
            FOREIGN KEY(plan_id) REFERENCES plans(id)
        )""")
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('welcome',?)",
                    ("Hello! Welcome to YOMA STORE. Use /buy to browse products.",))

def is_owner(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == OWNER_ID and OWNER_ID != 0)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Edit Welcome", callback_data="edit_welcome")],
        [InlineKeyboardButton("📂 Manage Categories", callback_data="cats")],
        [InlineKeyboardButton("📦 Manage Products", callback_data="products")],
        [InlineKeyboardButton("🔑 Manage Stock", callback_data="stock")],
        [InlineKeyboardButton("📊 Statistics", callback_data="stats")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key='welcome'").fetchone()
    welcome = row["value"] if row else "Welcome to YOMA STORE!"
    await update.message.reply_text(welcome + "\n\nSend /buy to browse products.")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ You are not authorized.")
        return
    context.user_data.clear()
    await update.message.reply_text("👑 YOMA BOT — Developer Admin Panel", reply_markup=admin_keyboard())

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        cats = con.execute("SELECT * FROM categories ORDER BY id").fetchall()
    if not cats:
        await update.message.reply_text("No categories available yet.")
        return
    kb = [[InlineKeyboardButton(c["name"], callback_data=f"shopcat:{c['id']}")] for c in cats]
    await update.message.reply_text("🛒 Choose a category:", reply_markup=InlineKeyboardMarkup(kb))

async def show_products(query, category_id):
    with db() as con:
        rows = con.execute("SELECT * FROM products WHERE category_id=? ORDER BY id", (category_id,)).fetchall()
    if not rows:
        await query.edit_message_text("No products in this category.")
        return
    kb = [[InlineKeyboardButton(p["name"], callback_data=f"shopprod:{p['id']}")] for p in rows]
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="shopback")])
    await query.edit_message_text("📦 Choose a product:", reply_markup=InlineKeyboardMarkup(kb))

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("shopcat:"):
        await show_products(q, int(data.split(":")[1]))
        return
    if data.startswith("shopprod:"):
        pid = int(data.split(":")[1])
        with db() as con:
            p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            plans = con.execute("""
                SELECT pl.*, (SELECT COUNT(*) FROM stock s WHERE s.plan_id=pl.id AND s.sold=0) AS qty
                FROM plans pl WHERE pl.product_id=? ORDER BY pl.id
            """, (pid,)).fetchall()
        if not p:
            await q.edit_message_text("Product not found.")
            return
        text = f"📦 {p['name']}\n{p['description']}\n\nChoose a plan:"
        kb = [[InlineKeyboardButton(f"{pl['title']} — ${pl['price']:.2f} (Stock: {pl['qty']})",
                                    callback_data=f"plan:{pl['id']}")] for pl in plans]
        kb.append([InlineKeyboardButton("⬅️ Back", callback_data=f"shopcat:{p['category_id']}")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("plan:"):
        await q.edit_message_text(
            "You selected this plan. Payment and automatic delivery are not connected yet. "
            "Configure a verified payment provider before accepting payments."
        )
        return
    if data == "shopback":
        await buy_from_query(q)
        return

    if not is_owner(update):
        await q.edit_message_text("⛔ You are not authorized.")
        return

    if data == "adminhome":
        context.user_data.clear()
        await q.edit_message_text("👑 Developer Admin Panel", reply_markup=admin_keyboard())
    elif data == "edit_welcome":
        context.user_data["action"] = "welcome"
        await q.edit_message_text("Send the new welcome message:")
    elif data == "cats":
        kb = [
            [InlineKeyboardButton("➕ Add category", callback_data="cat_add")],
            [InlineKeyboardButton("📋 List categories", callback_data="cat_list")],
            [InlineKeyboardButton("⬅️ Admin home", callback_data="adminhome")]
        ]
        await q.edit_message_text("📂 Category management", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "cat_add":
        context.user_data["action"] = "cat_add"
        await q.edit_message_text("Send the new category name:")
    elif data == "cat_list":
        with db() as con:
            rows = con.execute("SELECT * FROM categories ORDER BY id").fetchall()
        txt = "\n".join(f"{r['id']}. {r['name']}" for r in rows) or "No categories."
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="cats")]]))
    elif data == "products":
        with db() as con:
            cats = con.execute("SELECT * FROM categories ORDER BY id").fetchall()
        kb = [[InlineKeyboardButton(c["name"], callback_data=f"prodcat:{c['id']}")] for c in cats]
        kb += [[InlineKeyboardButton("⬅️ Admin home", callback_data="adminhome")]]
        await q.edit_message_text("Choose a category for product management:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("prodcat:"):
        cid = int(data.split(":")[1])
        context.user_data["category_id"] = cid
        kb = [
            [InlineKeyboardButton("➕ Add product", callback_data="prod_add")],
            [InlineKeyboardButton("📋 List products", callback_data=f"prod_list:{cid}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="products")]
        ]
        await q.edit_message_text("📦 Product management", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "prod_add":
        context.user_data["action"] = "prod_add"
        await q.edit_message_text("Send product name:")
    elif data.startswith("prod_list:"):
        cid = int(data.split(":")[1])
        with db() as con:
            rows = con.execute("SELECT * FROM products WHERE category_id=? ORDER BY id", (cid,)).fetchall()
        txt = "\n".join(f"{r['id']}. {r['name']}" for r in rows) or "No products."
        await q.edit_message_text(txt + "\n\nTo add plans, use /addplan PRODUCT_ID | PLAN | PRICE | DURATION",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"prodcat:{cid}")]]))
    elif data == "stock":
        await q.edit_message_text(
            "Add stock with:\n/addstock PLAN_ID | LICENSE_KEY\n\n"
            "List plans with:\n/plans",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin home", callback_data="adminhome")]])
        )
    elif data == "stats":
        with db() as con:
            cats = con.execute("SELECT COUNT(*) n FROM categories").fetchone()["n"]
            prods = con.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]
            plans = con.execute("SELECT COUNT(*) n FROM plans").fetchone()["n"]
            stock = con.execute("SELECT COUNT(*) n FROM stock WHERE sold=0").fetchone()["n"]
        await q.edit_message_text(
            f"📊 Statistics\nCategories: {cats}\nProducts: {prods}\nPlans: {plans}\nAvailable stock: {stock}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin home", callback_data="adminhome")]])
        )

async def buy_from_query(q):
    with db() as con:
        cats = con.execute("SELECT * FROM categories ORDER BY id").fetchall()
    kb = [[InlineKeyboardButton(c["name"], callback_data=f"shopcat:{c['id']}")] for c in cats]
    await q.edit_message_text("🛒 Choose a category:", reply_markup=InlineKeyboardMarkup(kb))

async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    action = context.user_data.get("action")
    value = update.message.text.strip()
    if action == "welcome":
        with db() as con:
            con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('welcome',?)", (value,))
        context.user_data.pop("action", None)
        await update.message.reply_text("✅ Welcome message updated.", reply_markup=admin_keyboard())
    elif action == "cat_add":
        with db() as con:
            con.execute("INSERT INTO categories(name) VALUES(?)", (value,))
        context.user_data.pop("action", None)
        await update.message.reply_text("✅ Category added.", reply_markup=admin_keyboard())
    elif action == "prod_add":
        cid = context.user_data.get("category_id")
        if not cid:
            context.user_data.pop("action", None)
            await update.message.reply_text("Category session expired. Open /admin again.")
            return
        with db() as con:
            con.execute("INSERT INTO products(category_id,name) VALUES(?,?)", (cid, value))
        context.user_data.pop("action", None)
        await update.message.reply_text("✅ Product added. Add a plan using:\n/addplan PRODUCT_ID | PLAN | PRICE | DURATION")

async def addplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    raw = " ".join(context.args)
    try:
        pid, title, price, duration = [x.strip() for x in raw.split("|", 3)]
        with db() as con:
            con.execute("INSERT INTO plans(product_id,title,price,duration) VALUES(?,?,?,?)",
                        (int(pid), title, float(price), duration))
        await update.message.reply_text("✅ Plan added.")
    except Exception:
        await update.message.reply_text("Format: /addplan PRODUCT_ID | PLAN | PRICE | DURATION\nExample: /addplan 1 | 1 hour | 0.10 | 1h")

async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    raw = " ".join(context.args)
    try:
        plan_id, key = raw.split("|", 1)
        with db() as con:
            con.execute("INSERT INTO stock(plan_id,license_key) VALUES(?,?)", (int(plan_id.strip()), key.strip()))
        await update.message.reply_text("✅ Stock key added.")
    except Exception:
        await update.message.reply_text("Format: /addstock PLAN_ID | LICENSE_KEY")

async def plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    with db() as con:
        rows = con.execute("""
            SELECT pl.id, pl.title, pl.price, pl.duration, p.name product
            FROM plans pl JOIN products p ON p.id=pl.product_id ORDER BY pl.id
        """).fetchall()
    txt = "\n".join(f"Plan {r['id']} — {r['product']} / {r['title']} / ${r['price']:.2f} / {r['duration']}" for r in rows)
    await update.message.reply_text(txt or "No plans yet.")

def main():
    if not BOT_TOKEN or OWNER_ID == 0:
        raise SystemExit("Set BOT_TOKEN and OWNER_ID environment variables first.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addplan", addplan))
    app.add_handler(CommandHandler("addstock", addstock))
    app.add_handler(CommandHandler("plans", plans))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))
    print("YOMA BOT is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
