# 🌌 Vybizo — The Next-Gen Hyperlocal Marketplace

![Vybizo Logo](https://img.shields.io/badge/Vybizo-Marketplace-A855F7?style=for-the-badge)
![Flask](https://img.shields.io/badge/Flask-3.0-white?style=for-the-badge&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite)
![Vercel/Render](https://img.shields.io/badge/Deployment-Ready-22C55E?style=for-the-badge)

Vybizo is a premium, high-fidelity hyperlocal marketplace designed to connect local businesses with their communities through a stunning, immersive interface. Built with a focus on "Aether" design aesthetics, Vybizo offers a cinematic shopping experience right in your neighborhood.

---

## ✨ Key Features

- **🚀 Smart Marketplace**: Real-time search and filtering for local products and businesses.
- **🛡️ Secure Auth**: Robust user registration and login system with hashed passwords and protected sessions.
- **🏬 Business Hub**: Comprehensive merchant profiles featuring social media integration (WhatsApp, Instagram, Facebook).
- **📹 Rich Media Support**: Seamlessly upload and showcase products with both high-resolution images and dynamic videos.
- **📍 GPS Integration**: Automatically detect business locations for accurate local discovery.
- **📱 Ultra-Responsive**: A "mobile-first" approach ensures the marketplace looks breathtaking on any device.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python / Flask |
| **Database** | SQLite3 |
| **Styling** | Vanilla CSS (God-Tier Design Tokens) |
| **Frontend** | Jinja2 & Dynamic JavaScript |
| **Security** | SHA-256 Hashing |
| **Deployment** | Vercel / Render / Railway |

---

## 🏁 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/jayanthchowdary2006/vybizo.git
cd vybizo
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Locally
```bash
python app.py
```
Visit `http://127.0.0.1:5000` in your browser.

---

## ☁️ Deployment Guide

Vybizo is pre-configured for modern serverless and container platforms.

### **Render / Railway**
- Connect your GitHub repo.
- Set **Build Command**: `pip install -r requirements.txt`
- Set **Start Command**: `gunicorn app:app`
- *Note: Vybizo automatically detects the environment and handles file paths for `/tmp/` storage.*

### **Vercel**
- Use the included `vercel.json` for zero-config deployment.

---

## 🎨 Design Philosophy
Vybizo utilizes a custom **"Aether"** design system characterized by:
- **Glassmorphism**: Elegant blur effects and translucent layers.
- **Kinetic Backgrounds**: Dynamic radial gradients that breathe life into the UI.
- **Vibrant Typography**: Syne and DM Sans for a modern, professional look.

---

## 📜 License
Developed as part of the Vybizo project. All rights reserved.

---

<p align="center">
  Made with 💜 for local communities.
</p>
