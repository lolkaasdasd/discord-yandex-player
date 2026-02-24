import tkinter as tk
from tkinter import messagebox
import json
import os

# Путь к файлу, который читает бот
BLACKLIST_FILE = "blacklist.json"

def load_data():
    if not os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'w') as f: json.dump([], f)
    try:
        with open(BLACKLIST_FILE, 'r') as f: return json.load(f)
    except: return []

def save_data(data):
    with open(BLACKLIST_FILE, 'w') as f:
        json.dump(data, f)

def refresh_list():
    listbox.delete(0, tk.END)
    for uid in load_data():
        listbox.insert(tk.END, str(uid))

def add_user():
    user_id = entry.get().strip()
    if not user_id.isdigit():
        messagebox.showerror("Ошибка", "ID должен состоять только из цифр!")
        return
        
    data = load_data()
    if user_id not in data:
        data.append(user_id)
        save_data(data)
        refresh_list()
        entry.delete(0, tk.END)
        messagebox.showinfo("Успех", f"Пользователь {user_id} заблокирован!")
    else:
        messagebox.showwarning("Внимание", "Этот ID уже в черном списке.")

def remove_user():
    selected = listbox.curselection()
    if not selected:
        messagebox.showerror("Ошибка", "Выберите ID из списка для удаления.")
        return
        
    user_id = listbox.get(selected[0])
    data = load_data()
    if user_id in data:
        data.remove(user_id)
        save_data(data)
        refresh_list()
        messagebox.showinfo("Успех", f"Пользователь {user_id} разблокирован!")

# --- Создание окна GUI ---
root = tk.Tk()
root.title("🛡️ Music Bot Admin Panel")
root.geometry("350x400")
root.configure(bg="#2b2d31")
root.resizable(False, False)

tk.Label(root, text="Черный список (ID пользователей)", bg="#2b2d31", fg="white", font=("Arial", 12, "bold")).pack(pady=10)

listbox = tk.Listbox(root, bg="#1e1f22", fg="white", font=("Consolas", 11), selectbackground="#5865F2")
listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

entry = tk.Entry(root, font=("Consolas", 12), justify="center")
entry.pack(pady=10, padx=20, fill=tk.X)

btn_frame = tk.Frame(root, bg="#2b2d31")
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="Забанить ID", bg="#ed4245", fg="white", font=("Arial", 10, "bold"), command=add_user).grid(row=0, column=0, padx=10)
tk.Button(btn_frame, text="Разбанить", bg="#3ba55c", fg="white", font=("Arial", 10, "bold"), command=remove_user).grid(row=0, column=1, padx=10)

refresh_list()
root.mainloop()