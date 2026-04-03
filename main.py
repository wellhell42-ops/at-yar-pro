"""
At Yarışı Pro Analiz  v15.0
━━━━━━━━━━━━━━━━━━━━━━━━━
• Yenibeygir günlük bülten otomatik çekim
• Koşu → At listesi → Galop + Stil + Performans
• TJK Trakus dereceleri çekimi + Tempo analizi
• Mesafe bazlı Trakus tempo referans verileri
• Geçmiş yarış tarama + mesafe/pist uyum analizi
• Jokey-at istatistikleri + momentum analizi
• Kapsamlı genel yarış analizi (birleşik güç puanı)
• Tesseract + Poppler otomatik kurulum (PDF için)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, os, re, sys, zipfile, subprocess, json
import urllib.request, urllib.error, urllib.parse
import http.cookiejar
from datetime import datetime, timedelta
import pandas as pd

try:
    from bs4 import BeautifulSoup
    BS4 = True
except ImportError:
    BS4 = False

# ─── Renkler ──────────────────────────────────────────────
BG      = "#0D1B2A"
PANEL   = "#152030"
CARD    = "#1A2A3D"
ACCENT  = "#E8212A"
GREEN   = "#27AE60"
BLUE    = "#2980B9"
GOLD    = "#F5A623"
SILVER  = "#95A5A6"
BRONZE  = "#CA6F1E"
TEAL    = "#16A085"
YELLOW  = "#F39C12"
ORANGE  = "#E67E22"
TEXT    = "#ECF0F1"
DIM     = "#7F8C9A"
BORDER  = "#1E3050"
RED     = "#E74C3C"

LINE_C = [ACCENT,GREEN,BLUE,GOLD,TEAL,ORANGE,"#9B59B6","#1ABC9C","#E67E22","#2ECC71"]

F_H  = ("Segoe UI", 14, "bold")   # heading
F_M  = ("Segoe UI", 10, "bold")   # medium
F_N  = ("Segoe UI", 9)            # normal
F_S  = ("Segoe UI", 9,  "bold")   # small bold
F_XS = ("Segoe UI", 8)            # tiny

APP_DIR     = os.path.dirname(os.path.abspath(sys.argv[0]))
POPPLER_DIR = os.path.join(APP_DIR, "poppler_bin")

TESS_URL = ("https://github.com/UB-Mannheim/tesseract/releases/download/"
            "v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe")
POP_URL  = ("https://github.com/oschwartz10612/poppler-windows/releases/download/"
            "v24.08.0-0/Release-24.08.0-0.zip")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36"),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

SEHIRLER = [
    "istanbul","ankara","izmir","bursa","adana",
    "kocaeli","diyarbakir","elazig","sanliurfa","konya","antalya","balikesir",
]

TAKI_ACIKLAMA = {
    "SKG":"Göz Koruyucu","SK":"Sun Koruyucu","DB":"Dil Bağı",
    "YP":"Yan Perde","KG":"Kör Gözlük","BP":"Burniye",
    "KBK":"Kör Başlık","T":"Tırnak","ÇR":"Çekildi",
}

TJK_SEHIR_ID = {
    "istanbul": "1", "ankara": "2", "izmir": "3", "bursa": "4",
    "adana": "5", "kocaeli": "6", "diyarbakir": "7", "elazig": "8",
    "sanliurfa": "9", "konya": "10", "antalya": "11", "balikesir": "12",
}

_tess = None
_pop  = None
_tjk_opener = None

# ─── Mesafe Bazlı Trakus Tempo Referans Verileri ─────────
# Her mesafe ve pist tipi için referans derece, seksiyonel hız
# ve tempo beklentileri.  Kaynaklar: TJK istatistikleri,
# ortalama koşu dereceleri ve seksiyonel analizler.
#
# Yapı: MESAFE_TEMPO_REF[mesafe][pist] = {
#   "ref_derece"    : (iyi, orta, zayıf)  — saniye cinsinden
#   "ort_hiz_ms"    : (iyi, orta, zayıf)  — m/s
#   "seksiyonlar"   : [(baslangic, bitis, ref_hiz_ms), ...]
#   "tempo_tipi"    : beklenen tempo profili açıklaması
#   "aciklama"      : mesafe karakteristiği
# }

MESAFE_TEMPO_REF = {
    1000: {
        "Kum": {
            "ref_derece": (58.0, 61.0, 64.0),
            "ort_hiz_ms": (17.24, 16.39, 15.63),
            "seksiyonlar": [
                (0, 200, 16.0), (200, 400, 17.2),
                (400, 600, 17.5), (600, 800, 17.8),
                (800, 1000, 17.0),
            ],
            "tempo_tipi": "Sprint — erken hız kritik, son 200m dayanıklılık",
            "aciklama": "Kısa mesafe sprint koşusu. Çıkış hızı ve erken pozisyon belirleyici.",
        },
        "Çim": {
            "ref_derece": (56.0, 59.0, 62.0),
            "ort_hiz_ms": (17.86, 16.95, 16.13),
            "seksiyonlar": [
                (0, 200, 16.5), (200, 400, 17.8),
                (400, 600, 18.0), (600, 800, 18.2),
                (800, 1000, 17.5),
            ],
            "tempo_tipi": "Sprint — çimde daha hızlı tempolar beklenir",
            "aciklama": "Çim pistte kısa mesafe. Zemin avantajı ile daha düşük dereceler.",
        },
        "Sentetik": {
            "ref_derece": (57.5, 60.5, 63.5),
            "ort_hiz_ms": (17.39, 16.53, 15.75),
            "seksiyonlar": [
                (0, 200, 16.2), (200, 400, 17.4),
                (400, 600, 17.7), (600, 800, 18.0),
                (800, 1000, 17.2),
            ],
            "tempo_tipi": "Sprint — sentetik pistte tutarlı zemin",
            "aciklama": "Sentetik pistte kısa mesafe. Tutarlı zemin koşulları.",
        },
    },
    1100: {
        "Kum": {
            "ref_derece": (64.5, 68.0, 71.5),
            "ort_hiz_ms": (17.05, 16.18, 15.38),
            "seksiyonlar": [
                (0, 200, 15.8), (200, 400, 17.0),
                (400, 600, 17.3), (600, 800, 17.5),
                (800, 1100, 16.8),
            ],
            "tempo_tipi": "Kısa-orta mesafe — çıkış ve dayanıklılık dengesi",
            "aciklama": "Sprint ile orta mesafe arası geçiş koşusu.",
        },
        "Çim": {
            "ref_derece": (62.5, 66.0, 69.5),
            "ort_hiz_ms": (17.60, 16.67, 15.83),
            "seksiyonlar": [
                (0, 200, 16.3), (200, 400, 17.5),
                (400, 600, 17.8), (600, 800, 18.0),
                (800, 1100, 17.3),
            ],
            "tempo_tipi": "Kısa-orta mesafe — çimde avantajlı",
            "aciklama": "Çim pistte kısa-orta mesafe koşusu.",
        },
        "Sentetik": {
            "ref_derece": (63.5, 67.0, 70.5),
            "ort_hiz_ms": (17.32, 16.42, 15.60),
            "seksiyonlar": [
                (0, 200, 16.0), (200, 400, 17.2),
                (400, 600, 17.5), (600, 800, 17.7),
                (800, 1100, 17.0),
            ],
            "tempo_tipi": "Kısa-orta mesafe — sentetik zemin",
            "aciklama": "Sentetik pistte kısa-orta mesafe koşusu.",
        },
    },
    1200: {
        "Kum": {
            "ref_derece": (70.0, 73.5, 77.0),
            "ort_hiz_ms": (17.14, 16.33, 15.58),
            "seksiyonlar": [
                (0, 200, 15.5), (200, 400, 16.8),
                (400, 600, 17.2), (600, 800, 17.5),
                (800, 1000, 17.3), (1000, 1200, 16.5),
            ],
            "tempo_tipi": "Sprint-orta — son 400m kapanış gücü önemli",
            "aciklama": "Klasik sprint mesafesi. Hız ve dayanıklılık dengesi.",
        },
        "Çim": {
            "ref_derece": (67.5, 71.0, 74.5),
            "ort_hiz_ms": (17.78, 16.90, 16.11),
            "seksiyonlar": [
                (0, 200, 16.0), (200, 400, 17.3),
                (400, 600, 17.8), (600, 800, 18.2),
                (800, 1000, 18.0), (1000, 1200, 17.0),
            ],
            "tempo_tipi": "Sprint-orta — çimde yüksek tempo",
            "aciklama": "Çim pistte sprint mesafesi. Daha hızlı dereceler.",
        },
        "Sentetik": {
            "ref_derece": (69.0, 72.5, 76.0),
            "ort_hiz_ms": (17.39, 16.55, 15.79),
            "seksiyonlar": [
                (0, 200, 15.7), (200, 400, 17.0),
                (400, 600, 17.5), (600, 800, 17.8),
                (800, 1000, 17.5), (1000, 1200, 16.7),
            ],
            "tempo_tipi": "Sprint-orta — sentetik zemin tutarlılığı",
            "aciklama": "Sentetik pistte sprint mesafesi.",
        },
    },
    1300: {
        "Kum": {
            "ref_derece": (77.0, 81.0, 85.0),
            "ort_hiz_ms": (16.88, 16.05, 15.29),
            "seksiyonlar": [
                (0, 200, 15.2), (200, 400, 16.5),
                (400, 600, 17.0), (600, 800, 17.3),
                (800, 1000, 17.0), (1000, 1300, 16.2),
            ],
            "tempo_tipi": "Orta mesafe — tempolu koşu, kapanış belirleyici",
            "aciklama": "Orta mesafe geçiş koşusu. Tempo yönetimi kritik.",
        },
        "Çim": {
            "ref_derece": (74.5, 78.0, 82.0),
            "ort_hiz_ms": (17.45, 16.67, 15.85),
            "seksiyonlar": [
                (0, 200, 15.8), (200, 400, 17.0),
                (400, 600, 17.5), (600, 800, 17.8),
                (800, 1000, 17.5), (1000, 1300, 16.8),
            ],
            "tempo_tipi": "Orta mesafe — çimde hızlı geçişler",
            "aciklama": "Çim pistte orta mesafe koşusu.",
        },
        "Sentetik": {
            "ref_derece": (76.0, 80.0, 84.0),
            "ort_hiz_ms": (17.11, 16.25, 15.48),
            "seksiyonlar": [
                (0, 200, 15.5), (200, 400, 16.8),
                (400, 600, 17.2), (600, 800, 17.5),
                (800, 1000, 17.2), (1000, 1300, 16.5),
            ],
            "tempo_tipi": "Orta mesafe — sentetik zemin",
            "aciklama": "Sentetik pistte orta mesafe koşusu.",
        },
    },
    1400: {
        "Kum": {
            "ref_derece": (83.0, 87.5, 92.0),
            "ort_hiz_ms": (16.87, 16.00, 15.22),
            "seksiyonlar": [
                (0, 200, 15.0), (200, 400, 16.2),
                (400, 600, 16.8), (600, 800, 17.2),
                (800, 1000, 17.0), (1000, 1200, 16.8),
                (1200, 1400, 16.2),
            ],
            "tempo_tipi": "Orta mesafe — mile klasiği, dengeli tempo ideal",
            "aciklama": "En popüler orta mesafe. Tempo kontrolü ve kapanış dengesi.",
        },
        "Çim": {
            "ref_derece": (80.0, 84.0, 88.0),
            "ort_hiz_ms": (17.50, 16.67, 15.91),
            "seksiyonlar": [
                (0, 200, 15.5), (200, 400, 16.8),
                (400, 600, 17.3), (600, 800, 17.8),
                (800, 1000, 17.8), (1000, 1200, 17.3),
                (1200, 1400, 16.8),
            ],
            "tempo_tipi": "Orta mesafe — çimde mile klasiği",
            "aciklama": "Çim pistte mile mesafesi. Yüksek kaliteli koşular.",
        },
        "Sentetik": {
            "ref_derece": (82.0, 86.0, 90.0),
            "ort_hiz_ms": (17.07, 16.28, 15.56),
            "seksiyonlar": [
                (0, 200, 15.2), (200, 400, 16.5),
                (400, 600, 17.0), (600, 800, 17.5),
                (800, 1000, 17.3), (1000, 1200, 17.0),
                (1200, 1400, 16.5),
            ],
            "tempo_tipi": "Orta mesafe — sentetik mile",
            "aciklama": "Sentetik pistte mile mesafesi.",
        },
    },
    1500: {
        "Kum": {
            "ref_derece": (90.0, 95.0, 100.0),
            "ort_hiz_ms": (16.67, 15.79, 15.00),
            "seksiyonlar": [
                (0, 200, 14.8), (200, 400, 16.0),
                (400, 600, 16.5), (600, 800, 17.0),
                (800, 1000, 17.0), (1000, 1200, 16.5),
                (1200, 1500, 16.0),
            ],
            "tempo_tipi": "Orta-uzun — dayanıklılık ön plana çıkar",
            "aciklama": "Orta-uzun mesafe. Dayanıklılık ve tempo yönetimi.",
        },
        "Çim": {
            "ref_derece": (87.0, 91.5, 96.0),
            "ort_hiz_ms": (17.24, 16.39, 15.63),
            "seksiyonlar": [
                (0, 200, 15.3), (200, 400, 16.5),
                (400, 600, 17.0), (600, 800, 17.5),
                (800, 1000, 17.5), (1000, 1200, 17.0),
                (1200, 1500, 16.5),
            ],
            "tempo_tipi": "Orta-uzun — çim pistte",
            "aciklama": "Çim pistte orta-uzun mesafe koşusu.",
        },
        "Sentetik": {
            "ref_derece": (89.0, 93.5, 98.0),
            "ort_hiz_ms": (16.85, 16.04, 15.31),
            "seksiyonlar": [
                (0, 200, 15.0), (200, 400, 16.2),
                (400, 600, 16.7), (600, 800, 17.2),
                (800, 1000, 17.2), (1000, 1200, 16.7),
                (1200, 1500, 16.2),
            ],
            "tempo_tipi": "Orta-uzun — sentetik zemin",
            "aciklama": "Sentetik pistte orta-uzun mesafe koşusu.",
        },
    },
    1600: {
        "Kum": {
            "ref_derece": (97.0, 102.0, 107.0),
            "ort_hiz_ms": (16.49, 15.69, 14.95),
            "seksiyonlar": [
                (0, 200, 14.5), (200, 400, 15.8),
                (400, 600, 16.3), (600, 800, 16.8),
                (800, 1000, 17.0), (1000, 1200, 16.8),
                (1200, 1400, 16.3), (1400, 1600, 15.5),
            ],
            "tempo_tipi": "Uzun — enerji yönetimi ve kapanış zamanlaması",
            "aciklama": "Uzun mesafe koşusu. Strateji ve dayanıklılık kritik.",
        },
        "Çim": {
            "ref_derece": (93.5, 98.0, 103.0),
            "ort_hiz_ms": (17.11, 16.33, 15.53),
            "seksiyonlar": [
                (0, 200, 15.0), (200, 400, 16.3),
                (400, 600, 16.8), (600, 800, 17.3),
                (800, 1000, 17.5), (1000, 1200, 17.3),
                (1200, 1400, 16.8), (1400, 1600, 16.0),
            ],
            "tempo_tipi": "Uzun — çimde yüksek hız",
            "aciklama": "Çim pistte uzun mesafe koşusu.",
        },
        "Sentetik": {
            "ref_derece": (95.5, 100.5, 105.5),
            "ort_hiz_ms": (16.75, 15.92, 15.17),
            "seksiyonlar": [
                (0, 200, 14.7), (200, 400, 16.0),
                (400, 600, 16.5), (600, 800, 17.0),
                (800, 1000, 17.2), (1000, 1200, 17.0),
                (1200, 1400, 16.5), (1400, 1600, 15.7),
            ],
            "tempo_tipi": "Uzun — sentetik zemin",
            "aciklama": "Sentetik pistte uzun mesafe koşusu.",
        },
    },
    1800: {
        "Kum": {
            "ref_derece": (111.0, 117.0, 123.0),
            "ort_hiz_ms": (16.22, 15.38, 14.63),
            "seksiyonlar": [
                (0, 200, 14.2), (200, 400, 15.5),
                (400, 600, 16.0), (600, 800, 16.5),
                (800, 1000, 16.8), (1000, 1200, 16.5),
                (1200, 1400, 16.0), (1400, 1600, 15.5),
                (1600, 1800, 15.0),
            ],
            "tempo_tipi": "Uzun — stayer karakteri, erken tempo riskli",
            "aciklama": "Uzun mesafe. Erken tempoda yorulma riski yüksek.",
        },
        "Çim": {
            "ref_derece": (107.0, 112.5, 118.0),
            "ort_hiz_ms": (16.82, 16.00, 15.25),
            "seksiyonlar": [
                (0, 200, 14.7), (200, 400, 16.0),
                (400, 600, 16.5), (600, 800, 17.0),
                (800, 1000, 17.2), (1000, 1200, 17.0),
                (1200, 1400, 16.5), (1400, 1600, 16.0),
                (1600, 1800, 15.5),
            ],
            "tempo_tipi": "Uzun — çim pistte stayer",
            "aciklama": "Çim pistte uzun mesafe stayer koşusu.",
        },
        "Sentetik": {
            "ref_derece": (109.5, 115.0, 121.0),
            "ort_hiz_ms": (16.44, 15.65, 14.88),
            "seksiyonlar": [
                (0, 200, 14.5), (200, 400, 15.7),
                (400, 600, 16.2), (600, 800, 16.7),
                (800, 1000, 17.0), (1000, 1200, 16.7),
                (1200, 1400, 16.2), (1400, 1600, 15.7),
                (1600, 1800, 15.2),
            ],
            "tempo_tipi": "Uzun — sentetik stayer",
            "aciklama": "Sentetik pistte uzun mesafe koşusu.",
        },
    },
    2000: {
        "Kum": {
            "ref_derece": (125.0, 132.0, 139.0),
            "ort_hiz_ms": (16.00, 15.15, 14.39),
            "seksiyonlar": [
                (0, 200, 13.8), (200, 400, 15.0),
                (400, 600, 15.5), (600, 800, 16.0),
                (800, 1000, 16.5), (1000, 1200, 16.5),
                (1200, 1400, 16.3), (1400, 1600, 16.0),
                (1600, 1800, 15.5), (1800, 2000, 15.0),
            ],
            "tempo_tipi": "Uzun stayer — enerji tasarrufu ve geç kapanış",
            "aciklama": "Klasik uzun mesafe. Sabırlı koşu ve güçlü kapanış.",
        },
        "Çim": {
            "ref_derece": (120.5, 127.0, 133.5),
            "ort_hiz_ms": (16.60, 15.75, 14.98),
            "seksiyonlar": [
                (0, 200, 14.3), (200, 400, 15.5),
                (400, 600, 16.0), (600, 800, 16.5),
                (800, 1000, 17.0), (1000, 1200, 17.0),
                (1200, 1400, 16.8), (1400, 1600, 16.5),
                (1600, 1800, 16.0), (1800, 2000, 15.5),
            ],
            "tempo_tipi": "Uzun stayer — çimde klasik mesafe",
            "aciklama": "Çim pistte klasik uzun mesafe koşusu.",
        },
        "Sentetik": {
            "ref_derece": (123.0, 130.0, 137.0),
            "ort_hiz_ms": (16.26, 15.38, 14.60),
            "seksiyonlar": [
                (0, 200, 14.0), (200, 400, 15.2),
                (400, 600, 15.7), (600, 800, 16.2),
                (800, 1000, 16.7), (1000, 1200, 16.7),
                (1200, 1400, 16.5), (1400, 1600, 16.2),
                (1600, 1800, 15.7), (1800, 2000, 15.2),
            ],
            "tempo_tipi": "Uzun stayer — sentetik",
            "aciklama": "Sentetik pistte uzun mesafe koşusu.",
        },
    },
    2200: {
        "Kum": {
            "ref_derece": (139.0, 147.0, 155.0),
            "ort_hiz_ms": (15.83, 14.97, 14.19),
            "seksiyonlar": [
                (0, 200, 13.5), (200, 400, 14.8),
                (400, 600, 15.3), (600, 800, 15.8),
                (800, 1000, 16.2), (1000, 1200, 16.5),
                (1200, 1400, 16.3), (1400, 1600, 16.0),
                (1600, 1800, 15.5), (1800, 2000, 15.0),
                (2000, 2200, 14.5),
            ],
            "tempo_tipi": "Maraton tipi — yüksek dayanıklılık gerektirir",
            "aciklama": "Çok uzun mesafe. Dayanıklılık ve soy kalitesi belirleyici.",
        },
        "Çim": {
            "ref_derece": (133.5, 141.0, 148.5),
            "ort_hiz_ms": (16.48, 15.60, 14.81),
            "seksiyonlar": [
                (0, 200, 14.0), (200, 400, 15.3),
                (400, 600, 15.8), (600, 800, 16.3),
                (800, 1000, 16.8), (1000, 1200, 17.0),
                (1200, 1400, 16.8), (1400, 1600, 16.5),
                (1600, 1800, 16.0), (1800, 2000, 15.5),
                (2000, 2200, 15.0),
            ],
            "tempo_tipi": "Maraton tipi — çimde uzun mesafe",
            "aciklama": "Çim pistte çok uzun mesafe koşusu.",
        },
        "Sentetik": {
            "ref_derece": (136.5, 144.0, 152.0),
            "ort_hiz_ms": (16.12, 15.28, 14.47),
            "seksiyonlar": [
                (0, 200, 13.7), (200, 400, 15.0),
                (400, 600, 15.5), (600, 800, 16.0),
                (800, 1000, 16.5), (1000, 1200, 16.7),
                (1200, 1400, 16.5), (1400, 1600, 16.2),
                (1600, 1800, 15.7), (1800, 2000, 15.2),
                (2000, 2200, 14.7),
            ],
            "tempo_tipi": "Maraton tipi — sentetik",
            "aciklama": "Sentetik pistte çok uzun mesafe koşusu.",
        },
    },
    2400: {
        "Kum": {
            "ref_derece": (153.0, 162.0, 171.0),
            "ort_hiz_ms": (15.69, 14.81, 14.04),
            "seksiyonlar": [
                (0, 200, 13.2), (200, 400, 14.5),
                (400, 600, 15.0), (600, 800, 15.5),
                (800, 1000, 16.0), (1000, 1200, 16.3),
                (1200, 1400, 16.3), (1400, 1600, 16.0),
                (1600, 1800, 15.5), (1800, 2000, 15.0),
                (2000, 2200, 14.5), (2200, 2400, 14.0),
            ],
            "tempo_tipi": "Derby mesafesi — sabır, strateji ve soy kalitesi",
            "aciklama": "Derby mesafesi. En yüksek dayanıklılık ve strateji.",
        },
        "Çim": {
            "ref_derece": (147.0, 155.0, 163.0),
            "ort_hiz_ms": (16.33, 15.48, 14.72),
            "seksiyonlar": [
                (0, 200, 13.7), (200, 400, 15.0),
                (400, 600, 15.5), (600, 800, 16.0),
                (800, 1000, 16.5), (1000, 1200, 16.8),
                (1200, 1400, 16.8), (1400, 1600, 16.5),
                (1600, 1800, 16.0), (1800, 2000, 15.5),
                (2000, 2200, 15.0), (2200, 2400, 14.5),
            ],
            "tempo_tipi": "Derby mesafesi — çim pistte klasik",
            "aciklama": "Çim pistte derby mesafesi koşusu.",
        },
        "Sentetik": {
            "ref_derece": (150.5, 159.0, 167.5),
            "ort_hiz_ms": (15.95, 15.09, 14.33),
            "seksiyonlar": [
                (0, 200, 13.5), (200, 400, 14.7),
                (400, 600, 15.2), (600, 800, 15.7),
                (800, 1000, 16.2), (1000, 1200, 16.5),
                (1200, 1400, 16.5), (1400, 1600, 16.2),
                (1600, 1800, 15.7), (1800, 2000, 15.2),
                (2000, 2200, 14.7), (2200, 2400, 14.2),
            ],
            "tempo_tipi": "Derby mesafesi — sentetik zemin",
            "aciklama": "Sentetik pistte derby mesafesi koşusu.",
        },
    },
}

def mesafe_tempo_bilgisi(mesafe: int, pist: str = "") -> dict | None:
    """Verilen mesafe ve pist tipi için referans tempo bilgisini döndür."""
    # Tam eşleşme
    if mesafe in MESAFE_TEMPO_REF:
        ref = MESAFE_TEMPO_REF[mesafe]
        if pist and pist in ref:
            return ref[pist]
        # Pist bulunamazsa ilk mevcut olanı döndür
        for p in ("Kum", "Çim", "Sentetik"):
            if p in ref:
                return ref[p]
    # En yakın mesafeyi bul
    if MESAFE_TEMPO_REF:
        en_yakin = min(MESAFE_TEMPO_REF.keys(),
                       key=lambda m: abs(m - mesafe))
        if abs(en_yakin - mesafe) <= 100:
            ref = MESAFE_TEMPO_REF[en_yakin]
            if pist and pist in ref:
                return ref[pist]
            for p in ("Kum", "Çim", "Sentetik"):
                if p in ref:
                    return ref[p]
    return None


def derece_formatla(saniye: float) -> str:
    """Saniyeyi M.SS.D formatına çevir."""
    if saniye >= 60:
        m = int(saniye // 60)
        s = saniye - m * 60
        return f"{m}.{s:05.2f}"
    return f"{saniye:.2f}"


# ─── Kurulum ──────────────────────────────────────────────

def find_tess():
    import shutil
    for p in [
        os.path.join(APP_DIR,"tesseract_bin","tesseract.exe"),
        shutil.which("tesseract") or "",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA",""),
                     "Programs","Tesseract-OCR","tesseract.exe"),
    ]:
        if p and os.path.exists(p): return p
    return None

def ensure_tess(cb):
    t = find_tess()
    if t: return t
    cb("Tesseract indiriliyor (~50MB)…")
    inst = os.path.join(APP_DIR,"tess_setup.exe")
    try:
        urllib.request.urlretrieve(TESS_URL, inst)
        cb("Tesseract kuruluyor…")
        subprocess.run([inst,"/S"], check=True, timeout=180)
    except Exception: pass
    finally:
        if os.path.exists(inst): os.remove(inst)
    return find_tess()

def ensure_pop(cb):
    import shutil
    if shutil.which("pdftoppm"): return ""
    if os.path.exists(os.path.join(POPPLER_DIR,"pdftoppm.exe")): return POPPLER_DIR
    cb("Poppler indiriliyor…")
    zp = os.path.join(APP_DIR,"pop.zip")
    try:
        urllib.request.urlretrieve(POP_URL, zp)
        with zipfile.ZipFile(zp) as z:
            os.makedirs(POPPLER_DIR, exist_ok=True)
            for m in z.namelist():
                if "/bin/" in m and not m.endswith("/"):
                    with z.open(m) as s, open(
                            os.path.join(POPPLER_DIR,os.path.basename(m)),"wb") as d:
                        d.write(s.read())
        return POPPLER_DIR
    except Exception: return None
    finally:
        if os.path.exists(zp): os.remove(zp)

def ensure_bs4(cb):
    global BS4
    if BS4: return True
    cb("beautifulsoup4 kuruluyor…")
    try:
        subprocess.run([sys.executable,"-m","pip","install",
                        "beautifulsoup4","--quiet"], check=True, timeout=60)
        from bs4 import BeautifulSoup
        BS4 = True
        return True
    except Exception: return False


# ─── Yardımcı ─────────────────────────────────────────────

def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def sehir_url(s: str) -> str:
    return (s.lower()
             .replace("ı","i").replace("ş","s").replace("ç","c")
             .replace("ğ","g").replace("ö","o").replace("ü","u")
             .replace(" ","-"))

def tarih_url(t: str) -> str:
    """GG.AA.YYYY → GG-AA-YYYY"""
    return t.replace(".","-")

def parse_date_key(d: str) -> str:
    try: p=d.split("."); return f"{p[2]}-{p[1]}-{p[0]}"
    except: return "0000-00-00"

def gun_farki(tarih: str) -> int | None:
    try:
        dt = datetime.strptime(tarih, "%d.%m.%Y")
        return (datetime.now() - dt).days
    except: return None

def bugun() -> str:
    return datetime.now().strftime("%d.%m.%Y")


# ─── Yenibeygir Scraper ───────────────────────────────────

def scrape_bulten(tarih: str, sehir: str) -> dict:
    """
    Günlük bülteni çek.
    Yenibeygir yapısı: koşu meta verisi tablo öncesi düz metin olarak gelir,
    her tablo bir koşunun at listesidir.
    """
    from bs4 import BeautifulSoup
    url  = f"https://yenibeygir.com/{tarih_url(tarih)}/{sehir_url(sehir)}"
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    # ── At tablosu olan tabloları bul ─────────────────────
    # Her tablo AGF | No | At İsmi | ... başlığı taşır
    at_tablolari = []
    for table in soup.find_all("table"):
        header_txt = table.get_text(" ")
        if "AGF" in header_txt and "At" in header_txt:
            at_tablolari.append(table)

    if not at_tablolari:
        raise Exception(
            f"Bülten tablosu bulunamadı.\n"
            f"URL: {url}\n\n"
            f"Olası nedenler:\n"
            f"• Bugün bu şehirde yarış yok\n"
            f"• Tarih formatı yanlış (GG.AA.YYYY olmalı)\n"
            f"• Şehir adı yanlış"
        )

    # ── Her tablo için koşu meta verisini önceki elementlerden çıkar ──
    kosular = []
    for kosu_no, table in enumerate(at_tablolari, start=1):
        # Tablo öncesindeki text node'lardan saat + cins + mesafe çıkar
        meta_txt = ""
        for sib in table.find_all_previous(limit=25):
            t = sib.get_text(" ", strip=True)
            if not t: continue
            # Önceki tabloya gelinirse dur
            if sib.name == "table": break
            meta_txt = t + " " + meta_txt

        saat_m  = re.search(r"(\d{2}:\d{2})", meta_txt)
        saat    = saat_m.group(1) if saat_m else ""

        para_m  = re.search(r"₺\s*([\d\.\,]+)", meta_txt)
        para    = "₺" + para_m.group(1) if para_m else ""

        # Mesafe + pist: "1400 Kum" veya "1400 Çim"
        msf_m   = re.search(r"(\d{3,5})\s*(Kum|Çim|Sentetik|Toprak|Sulu)?", meta_txt)
        mesafe  = msf_m.group(1) if msf_m else ""
        pist_t  = msf_m.group(2) if msf_m and msf_m.group(2) else ""

        # Koşu cinsi: "Maiden", "Handikap", "Şartlı" vb.
        cins_m  = re.search(
            r"(Maiden|Handikap|Hnd\.?|Şartlı|ŞARTLI|Satış|SATIŞ|Grup|Deneme|Açık)",
            meta_txt, re.I)
        cins    = cins_m.group(1) if cins_m else ""

        # Koşu no'yu metinden almaya çalış: tablo öncesi rakam
        no_m = re.search(r"\b(\d{1,2})\s*\.\s*(?:\d{2}:\d{2}|Koşu)", meta_txt)
        if no_m:
            kosu_no = int(no_m.group(1))

        kosu = {
            "no":     kosu_no,
            "saat":   saat,
            "cins":   cins,
            "mesafe": mesafe,
            "pist":   pist_t,
            "para":   para,
            "atlar":  [],
        }

        # ── Tablodan atları çıkar ─────────────────────────
        trs = table.find_all("tr")
        for tr in trs:
            tds = tr.find_all("td")
            if len(tds) < 5: continue
            cells = [td.get_text(" ", strip=True) for td in tds]

            # AGF: sayı veya "-" veya "0"
            agf = cells[0].strip()
            if not agf or not re.match(r"^[\d\.\,\-]+$", agf):
                continue

            # At linki ve ID
            at_id  = ""
            at_url = ""
            for a in tr.select("a[href*='/at/']"):
                m = re.match(r".*/at/(\d+)/([^\s\"'?#]+)", a.get("href",""))
                if m:
                    at_id  = m.group(1)
                    at_url = f"https://yenibeygir.com/at/{at_id}/{m.group(2)}"
                    break

            # At hücresi (genellikle index 2)
            at_cell = tds[2].get_text(" ", strip=True) if len(tds) > 2 else ""

            # Takı kodlarını çıkar
            takiler = re.findall(
                r"\b(SKG|SK|DB|YP|KG|BP|KBK|ÇR)\b", at_cell)
            taki = " ".join(dict.fromkeys(takiler))

            # At adı: büyük harf kelimeler, pedigri ve takıdan önce
            at_adi = ""
            if at_url:
                # URL slug'undan at adını al (en güvenilir)
                slug  = at_url.rstrip("/").split("/")[-1]
                at_adi= slug.replace("-"," ").upper()
            if not at_adi:
                # at_cell'den ilk büyük harf bloğu
                m = re.match(r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s\(\)]{1,35}?)(?:\s+(?:SKG|SK|DB|KG|YP|K\s|[A-Z]{2,3}\s)|$)",
                             at_cell)
                at_adi = m.group(1).strip() if m else at_cell[:25].strip()

            if not at_adi: continue

            # Son 10 bağlantılı sayılar
            son10 = []
            son10_td = tds[9] if len(tds) > 9 else (tds[8] if len(tds) > 8 else None)
            if son10_td:
                for a in son10_td.find_all("a"):
                    t2 = a.get_text(strip=True)
                    if t2.isdigit():
                        son10.append(int(t2))

            kosu["atlar"].append({
                "agf":      agf,
                "no":       cells[1].strip() if len(cells) > 1 else "",
                "at":       at_adi,
                "at_id":    at_id,
                "at_url":   at_url,
                "yas":      cells[3].strip() if len(cells) > 3 else "",
                "kilo":     cells[4].strip() if len(cells) > 4 else "",
                "jokey":    cells[5].strip() if len(cells) > 5 else "",
                "klv":      cells[7].strip() if len(cells) > 7 else "",
                "son10":    son10,
                "son10_str":"-".join(str(s) for s in son10) if son10 else "—",
                "hnd":      cells[10].strip() if len(cells) > 10 else "",
                "taki":     taki,
                "s":        cells[12].strip() if len(cells) > 12 else "",
            })

        if kosu["atlar"]:
            kosular.append(kosu)

    return {"tarih": tarih, "sehir": sehir, "kosular": kosular}


def scrape_galoplar(tarih: str, sehir: str, kosu_no: int) -> list:
    """Koşunun galop sayfasını çek — birden fazla URL pattern dener."""
    from bs4 import BeautifulSoup

    sehir_s = sehir_url(sehir)
    tarih_s = tarih_url(tarih)

    # Yenibeygir URL pattern'leri (yapı değişebilir)
    urls = [
        f"https://yenibeygir.com/{tarih_s}/{sehir_s}/{kosu_no}/galoplar",
        f"https://yenibeygir.com/{tarih_s}/{sehir_s}/{kosu_no}/galop",
        f"https://www.yenibeygir.com/{tarih_s}/{sehir_s}/{kosu_no}/galoplar",
    ]

    html = None
    last_err = ""
    for url in urls:
        try:
            html = fetch(url)
            if html and len(html) > 200:
                break
        except Exception as e:
            last_err = str(e)
            continue

    if not html or len(html) < 200:
        raise Exception(
            f"Galop sayfası açılamadı.\n"
            f"Denenen URL'ler:\n" +
            "\n".join(f"  • {u}" for u in urls) +
            f"\n\nHata: {last_err}\n"
            f"Olası nedenler:\n"
            f"• Bugün {sehir.title()}'da yarış yok\n"
            f"• Site yapısı değişmiş olabilir\n"
            f"• İnternet bağlantısı kontrol edin")

    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    if not tables:
        # Tablo yoksa div tabanlı yapıyı dene
        divs = soup.find_all("div", class_=re.compile(r"galop|race|horse", re.I))
        if not divs:
            raise Exception(
                f"Galop tablosu bulunamadı.\n"
                f"Sayfa boyutu: {len(html)} byte\n"
                f"Site yapısı değişmiş olabilir.")

    rows = []
    cur_at = ""
    cur_no = ""
    cur_url= ""

    # At URL haritası
    horse_urls = {}
    for a in soup.select("a[href*='/at/']"):
        href = a.get("href","")
        m = re.match(r".*/at/(\d+)/([^\s\"']+)", href)
        if m:
            at_txt = a.get_text(strip=True).upper()
            if at_txt:
                full_url = href if href.startswith("http") else f"https://yenibeygir.com{href}"
                horse_urls[at_txt] = full_url

    col_keys = ["400","600","800","1000","1200","1400"]

    # Tüm tablolarda galop verisi ara
    for table in tables:
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td","th"])
            if not tds: continue
            text0 = tds[0].get_text(" ", strip=True)

            # At başlık satırı — esnek regex
            if len(tds) <= 5 and re.search(r"[A-ZÇĞİÖŞÜ]{3,}", text0):
                m = re.match(r"(\d+)\s+([A-ZÇĞİÖŞÜa-zçğıöşü\s\(\)\-']+)", text0)
                if m:
                    cur_no  = m.group(1).strip()
                    cur_at  = m.group(2).strip().upper()
                    cur_url = horse_urls.get(cur_at, "")
                continue

            # Galop veri satırı
            if len(tds) >= 6:
                cells = [td.get_text(" ", strip=True) for td in tds]
                if not re.match(r"\d{2}\.\d{2}\.\d{4}", cells[0]): continue
                if not cur_at: continue

                row = {
                    "kosu_no": kosu_no,
                    "no":      cur_no,
                    "at":      cur_at,
                    "at_url":  cur_url,
                    "g_tarih": cells[0],
                    "g_sehir": cells[1] if len(cells)>1 else "",
                    "kg":      cells[2] if len(cells)>2 else "",
                    "jokey":   cells[3] if len(cells)>3 else "",
                    "cikis":   cells[-2] if len(cells)>=2 else "",
                    "pist":    cells[-1],
                }
                for i, k in enumerate(col_keys):
                    v = cells[4+i] if (4+i) < len(cells) else ""
                    row[k] = v if v not in ("-","","Kenter","ÇR","R") else ""
                rows.append(row)

        if rows:
            break  # İlk geçerli tabloyu bulduk

    if not rows:
        raise Exception(
            f"Galop verisi parse edilemedi.\n"
            f"Tablo sayısı: {len(tables)}\n"
            f"Olası nedenler:\n"
            f"• Bu koşu için galop kaydı yok\n"
            f"• Yenibeygir sayfa yapısı değişmiş")

    return rows


def scrape_profil(url: str) -> dict:
    """At profil sayfasını çek — yarış geçmişi + pist stats."""
    from bs4 import BeautifulSoup
    html  = fetch(url)
    soup  = BeautifulSoup(html, "html.parser")

    h2    = soup.find("h2")
    at_adi= h2.get_text(strip=True) if h2 else ""

    # Meta
    hnd = dozaj = ""
    for line in soup.get_text("\n").splitlines():
        line = line.strip()
        m = re.search(r"Handikap P[:\s]+(\d+)", line)
        if m: hnd = m.group(1)
        m = re.search(r"Dozaj P[:\s]+([\d\-]+)", line)
        if m: dozaj = m.group(1)

    # Yarış geçmişi tablosu
    races = []
    for table in soup.find_all("table"):
        trs   = table.find_all("tr")
        hmap  = {}
        htr   = None
        for tr in trs:
            cells = [td.get_text(strip=True) for td in tr.find_all(["th","td"])]
            if "Tarih" in cells and ("S" in cells or "Derece" in cells):
                hmap = {v:i for i,v in enumerate(cells)}
                htr  = tr
                break
        if not hmap: continue

        def gc(cells, *keys):
            for k in keys:
                i = hmap.get(k)
                if i is not None and i < len(cells): return cells[i]
            return ""

        for tr in trs:
            if tr is htr: continue
            tds   = tr.find_all("td")
            cells = [td.get_text(" ", strip=True) for td in tds]
            if not cells: continue
            tarih = gc(cells,"Tarih")
            if not tarih or not re.match(r"\d{2}\.\d{2}\.\d{4}", tarih): continue

            msf_raw = gc(cells,"Msf/Pist","Msf","Mesafe")
            msf_m   = re.search(r"(\d{3,5})", msf_raw)
            pist_m  = re.sub(r"[\d\s]","",msf_raw).strip()

            races.append({
                "tarih":  tarih,
                "sehir":  gc(cells,"Şehir","Sehir"),
                "kcins":  gc(cells,"K. Cinsi","KCins"),
                "msf":    msf_m.group(1) if msf_m else "",
                "pist":   pist_m,
                "sira":   gc(cells,"S","Sıra"),
                "derece": gc(cells,"Derece"),
                "hiz":    gc(cells,"Hız","Hiz"),
                "jokey":  gc(cells,"Jokey"),
                "kilo":   gc(cells,"Kilo"),
                "taki":   gc(cells,"Takı","Taki"),
            })
        if races: break

    # Pist istatistikleri
    pist_stats = {}
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells and cells[0] in ("Kum","Çim","Sentetik","Toplam"):
                try:
                    pist_stats[cells[0]] = {
                        "kosu": int(cells[1]) if len(cells)>1 else 0,
                        "1":    int(cells[2]) if len(cells)>2 else 0,
                        "2":    int(cells[3]) if len(cells)>3 else 0,
                        "3":    int(cells[4]) if len(cells)>4 else 0,
                        "hiz":  int(cells[7]) if len(cells)>7 else 0,
                    }
                except: pass

    return {"at": at_adi, "hnd": hnd, "dozaj": dozaj,
            "races": races, "pist_stats": pist_stats}


# ─── TJK Trakus Scraper ─────────────────────────────────

def _get_tjk_opener():
    """TJK oturum yönetimli opener — cookie persistance."""
    global _tjk_opener
    if _tjk_opener is None:
        cj = http.cookiejar.CookieJar()
        _tjk_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj))
    return _tjk_opener


def fetch_tjk(url: str, data: dict = None, timeout: int = 25) -> str:
    """TJK.org session-aware fetch — önce ana sayfaya gidip cookie alır."""
    opener = _get_tjk_opener()
    hdrs = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": "https://www.tjk.org/TR/YarisSonuclari/Index",
        "X-Requested-With": "XMLHttpRequest",
    }
    # Oturum oluştur (ilk ziyaret)
    try:
        init_req = urllib.request.Request(
            "https://www.tjk.org/TR/YarisSonuclari/Index",
            headers={k: v for k, v in hdrs.items()
                     if k != "X-Requested-With"})
        opener.open(init_req, timeout=timeout)
    except Exception:
        pass

    if data:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded, headers=hdrs)
        req.add_header("Content-Type",
                       "application/x-www-form-urlencoded; charset=UTF-8")
    else:
        req = urllib.request.Request(url, headers=hdrs)
    resp = opener.open(req, timeout=timeout)
    return resp.read().decode("utf-8", errors="replace")


def scrape_tjk_sonuclar(tarih: str, sehir: str) -> list:
    """
    TJK.org'dan günlük yarış sonuçlarını ve Trakus split verilerini çek.
    Returns: [{kosu_no, mesafe, pist, atlar: [{at, jokey, sira, derece, fark,
               splits:{200:t,400:t,...}, pozisyonlar:{200:p,400:p,...}}]}]
    """
    from bs4 import BeautifulSoup

    sehir_low = sehir_url(sehir)
    sehir_id = TJK_SEHIR_ID.get(sehir_low, "")
    if not sehir_id:
        raise Exception(f"TJK şehir bulunamadı: {sehir}")

    parts = tarih.split(".")
    tjk_tarih = f"{parts[0]}/{parts[1]}/{parts[2]}"

    # Birden fazla endpoint dene (TJK yapısı değişebilir)
    endpoints = [
        ("https://www.tjk.org/TR/YarisSonuclari/Query/ConnectedPage/"
         "GunlukYarisSonworker",
         {"QueryParameter_Ession": "",
          "QueryParameter_SehirId": sehir_id,
          "QueryParameter_YarisGunu": tjk_tarih,
          "QueryParameter_KosuNo": ""}),
        (f"https://www.tjk.org/TR/YarisSonuclari/GunlukYarisSonuclari"
         f"?SehirId={sehir_id}"
         f"&YarisGunu={urllib.parse.quote(tjk_tarih)}", None),
    ]

    html = None
    last_err = ""
    for url, post_data in endpoints:
        try:
            html = fetch_tjk(url, post_data)
            if html and len(html) > 500:
                break
        except Exception as e:
            last_err = str(e)
            continue

    if not html or len(html) < 200:
        raise Exception(
            f"TJK'dan veri alınamadı.\n"
            f"Şehir: {sehir} (ID: {sehir_id}), Tarih: {tarih}\n"
            f"Hata: {last_err}\n\n"
            f"TJK.org erişimi geçici engellenmiş olabilir."
        )

    soup = BeautifulSoup(html, "html.parser")
    kosular = []

    # ── Koşu meta (mesafe, pist) çıkarma ─────────────────
    kosu_meta = {}
    for elem in soup.find_all(["p", "div", "h2", "h3", "span", "strong"]):
        txt = elem.get_text(" ", strip=True)
        no_m = re.search(r"\b(\d{1,2})\s*\.\s*(?:Koşu|koşu|\d{2}:\d{2})", txt)
        msf_m = re.search(r"(\d{3,5})\s*(Kum|Çim|Sentetik|Toprak)?", txt)
        if no_m and msf_m:
            kno = int(no_m.group(1))
            kosu_meta[kno] = {
                "mesafe": msf_m.group(1),
                "pist": msf_m.group(2) or "",
            }

    # ── Tabloları parse et ─────────────────────────────────
    tables = soup.find_all("table")
    kosu_no = 0

    for table in tables:
        trs = table.find_all("tr")
        if len(trs) < 3:
            continue

        # Header bul
        header_cells = []
        header_tr = None
        for tr in trs:
            cells = [c.get_text(strip=True)
                     for c in tr.find_all(["th", "td"])]
            has_at = any(c in ("At Adı", "At", "Atın Adı", "İsim")
                         for c in cells)
            has_dist = any(re.match(r"^\d{3,4}$", c) for c in cells)
            has_derece = any(c in ("Derece", "Bitiş", "Der.") for c in cells)
            has_sira = any(c in ("S.", "S", "Sıra") for c in cells)

            if (has_at or has_sira) and (has_dist or has_derece):
                header_cells = cells
                header_tr = tr
                break

        if not header_cells:
            continue

        kosu_no += 1
        hmap = {v: i for i, v in enumerate(header_cells)}

        # Mesafe sütunlarını bul (200, 400, 600, 800, ...)
        dist_cols = {}
        for h in header_cells:
            m = re.match(r"^(\d{3,4})$", h)
            if m:
                dist_cols[int(m.group(1))] = hmap[h]

        atlar = []
        for tr in trs:
            if tr is header_tr:
                continue
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            cells = [td.get_text(" ", strip=True) for td in tds]

            def _gc(*keys):
                for k in keys:
                    idx = hmap.get(k)
                    if idx is not None and idx < len(cells):
                        return cells[idx]
                return ""

            at_adi = _gc("At Adı", "At", "Atın Adı", "İsim")
            if not at_adi or not re.search(
                    r"[A-Za-zÇĞİÖŞÜçğıöşü]", at_adi):
                continue

            sira = _gc("S.", "S", "Sıra")
            derece = _gc("Derece", "Bitiş", "Der.")
            jokey = _gc("Jokey", "J.")
            fark = _gc("Fark", "F.")
            kilo = _gc("Kilo", "Kg")

            # Trakus split zamanları parse et
            splits = {}
            pozisyonlar = {}
            for dist, col_idx in sorted(dist_cols.items()):
                if col_idx >= len(cells):
                    continue
                val = cells[col_idx].strip()
                if not val or val == "-":
                    continue
                # Format: "2 (23.45)" → poz=2, zaman=23.45
                m = re.match(r"(\d+)\s*[\(\[]"
                             r"([\d]+[:\.,][\d\.]+)\s*[\)\]]", val)
                if m:
                    pozisyonlar[dist] = int(m.group(1))
                    t_str = m.group(2).replace(",", ".")
                    t_sec = galop_to_sec(t_str) or derece_to_sec(t_str)
                    if t_sec:
                        splits[dist] = t_sec
                else:
                    # Sadece süre veya sadece pozisyon
                    t_sec = galop_to_sec(val) or derece_to_sec(val)
                    if t_sec:
                        splits[dist] = t_sec
                    else:
                        try:
                            pozisyonlar[dist] = int(val)
                        except ValueError:
                            pass

            atlar.append({
                "at": at_adi.strip().upper(),
                "sira": sira,
                "jokey": jokey,
                "derece": derece,
                "fark": fark,
                "kilo": kilo,
                "splits": splits,
                "pozisyonlar": pozisyonlar,
            })

        if atlar:
            meta = kosu_meta.get(kosu_no, {})
            kosular.append({
                "kosu_no": kosu_no,
                "mesafe": meta.get("mesafe", ""),
                "pist": meta.get("pist", ""),
                "atlar": atlar,
            })

    if not kosular:
        raise Exception(
            f"TJK sonuç tablosu parse edilemedi.\n"
            f"Sayfa boyutu: {len(html)} byte\n"
            f"Tablo sayısı: {len(tables)}\n\n"
            f"Olası nedenler:\n"
            f"• Bugün {sehir.title()}'da yarış yok veya henüz bitmedi\n"
            f"• TJK sayfa yapısı değişmiş olabilir"
        )

    return kosular


# ─── Tempo Analizi ───────────────────────────────────────

def analiz_tempo(tjk_kosular: list, profiller: dict = None) -> dict:
    """
    Trakus split verilerinden + profil geçmişinden tempo analizi.

    Çıktı (at bazında):
      seksiyonlar     : [{baslangic, bitis, mesafe, sure, hiz_ms}]
      ort_hiz, max_hiz, min_hiz
      erken_pace, gec_pace, pace_fark
      tempo_profil    : "🟢 KAPANIŞ" / "🔴 ERKEN TEMPO" / "🟡 DENGELİ"
      son_200_hiz, son_400_hiz
      tempo_skor      : 0-100
      poz_degisim     : gained positions (+ = öne geçti)
    """
    result = {}

    # ── 1) TJK Trakus verisi ──
    for kosu in (tjk_kosular or []):
        kosu_no = kosu["kosu_no"]
        try:
            kosu_mesafe = int(kosu.get("mesafe", "0"))
        except (ValueError, TypeError):
            kosu_mesafe = 0

        for at_data in kosu.get("atlar", []):
            at_adi = at_data["at"]
            splits = at_data.get("splits", {})
            pozlar = at_data.get("pozisyonlar", {})
            derece = at_data.get("derece", "")

            if not splits:
                continue

            distances = sorted(splits.keys())
            if len(distances) < 2:
                continue

            seksiyonlar = []
            prev_dist, prev_time = 0, 0.0
            for dist in distances:
                t = splits[dist]
                s_dist = dist - prev_dist
                s_time = t - prev_time
                if s_time > 0 and s_dist > 0:
                    seksiyonlar.append({
                        "baslangic": prev_dist,
                        "bitis": dist,
                        "mesafe": s_dist,
                        "sure": round(s_time, 2),
                        "hiz_ms": round(s_dist / s_time, 2),
                    })
                prev_dist, prev_time = dist, t

            # Son bölüm (son split → bitiş)
            total_sec = derece_to_sec(derece)
            if total_sec and distances and kosu_mesafe:
                kalan_m = kosu_mesafe - distances[-1]
                kalan_s = total_sec - splits[distances[-1]]
                if kalan_s > 0.5 and kalan_m > 0:
                    seksiyonlar.append({
                        "baslangic": distances[-1],
                        "bitis": kosu_mesafe,
                        "mesafe": kalan_m,
                        "sure": round(kalan_s, 2),
                        "hiz_ms": round(kalan_m / kalan_s, 2),
                    })

            if not seksiyonlar:
                continue

            kosu_pist = kosu.get("pist", "")
            r = _tempo_hesapla(at_adi, kosu_no, at_data, seksiyonlar,
                               pozlar, kosu_mesafe=kosu_mesafe,
                               kosu_pist=kosu_pist)
            result[at_adi] = r

    # ── 2) Profil verilerinden tempo tahmini (Trakus yoksa) ──
    if profiller:
        for at_adi, profil in profiller.items():
            if at_adi in result:
                continue  # Trakus verisi varsa gerek yok
            races = sorted(profil.get("races", []),
                           key=lambda r: parse_date_key(r.get("tarih", "")),
                           reverse=True)[:3]
            for race in races:
                d_sec = derece_to_sec(race.get("derece", ""))
                try:
                    msf = int(re.sub(r"[^\d]", "",
                                     str(race.get("msf", "") or "")))
                except (ValueError, TypeError):
                    msf = 0
                if not d_sec or not msf:
                    continue

                # Tahmini seksiyonel: eşit dağılım varsayımı + son bölüm
                n_sec = max(2, msf // 200)
                sec_dist = msf / n_sec
                sec_time = d_sec / n_sec
                base_hiz = msf / d_sec

                seksiyonlar = []
                for i in range(n_sec):
                    # Erken bölüm biraz hızlı, son bölüm yavaşlar varsayımı
                    frac = i / max(n_sec - 1, 1)
                    mod = 1.03 - frac * 0.06  # %3 hızlı → %3 yavaş
                    seksiyonlar.append({
                        "baslangic": int(i * sec_dist),
                        "bitis": int((i + 1) * sec_dist),
                        "mesafe": int(sec_dist),
                        "sure": round(sec_time / mod, 2),
                        "hiz_ms": round(base_hiz * mod, 2),
                    })

                pist_raw = re.sub(r"[\d\s]", "",
                                   str(race.get("msf", "") or "")).strip()
                r = _tempo_hesapla(at_adi, 0,
                                   {"sira": race.get("sira", ""),
                                    "derece": race.get("derece", ""),
                                    "fark": "", "jokey": race.get("jokey", ""),
                                    "kilo": race.get("kilo", ""),
                                    "splits": {}, "pozisyonlar": {}},
                                   seksiyonlar, {},
                                   kaynak="profil",
                                   kosu_mesafe=msf,
                                   kosu_pist=pist_raw)
                result[at_adi] = r
                break  # ilk geçerli yarışı al

    return result


def _tempo_hesapla(at_adi, kosu_no, at_data, seksiyonlar, pozlar,
                   kaynak="trakus", kosu_mesafe=0, kosu_pist=""):
    """Seksiyonel veriden tempo metrikleri hesapla + mesafe referans karşılaştırması."""
    hizlar = [s["hiz_ms"] for s in seksiyonlar]
    ort_hiz = sum(hizlar) / len(hizlar)
    max_hiz = max(hizlar)
    min_hiz = min(hizlar)

    # Erken pace vs Geç pace
    mid = len(seksiyonlar) // 2
    if mid > 0 and len(seksiyonlar) > mid:
        early = sum(s["hiz_ms"] for s in seksiyonlar[:mid]) / mid
        late_n = len(seksiyonlar) - mid
        late = sum(s["hiz_ms"] for s in seksiyonlar[mid:]) / late_n
    else:
        early = late = ort_hiz

    pace_diff = late - early

    if pace_diff > 0.4:
        tempo_profil = "🟢 KAPANIŞ"
    elif pace_diff < -0.4:
        tempo_profil = "🔴 ERKEN TEMPO"
    else:
        tempo_profil = "🟡 DENGELİ"

    son_200 = seksiyonlar[-1]["hiz_ms"] if seksiyonlar else None
    son_400 = (sum(s["hiz_ms"] for s in seksiyonlar[-2:]) /
               min(2, len(seksiyonlar))) if len(seksiyonlar) >= 2 else None

    # Tempo skoru (0-100)
    skor = 50.0
    skor += min(20, pace_diff * 12)           # Kapanış bonusu
    skor += min(15, (ort_hiz - 14) * 5)       # Genel hız
    skor += min(10, (max_hiz - ort_hiz) * 8)  # Patlama gücü
    if son_200 and son_200 > ort_hiz:
        skor += 5
    skor = round(max(0, min(100, skor)), 1)

    # Pozisyon değişimi
    poz_degisim = None
    if pozlar:
        poz_list = [(d, pozlar[d]) for d in sorted(pozlar.keys())]
        if len(poz_list) >= 2:
            poz_degisim = poz_list[0][1] - poz_list[-1][1]

    # ── Mesafe Referans Karşılaştırması ──
    ref = mesafe_tempo_bilgisi(kosu_mesafe, kosu_pist) if kosu_mesafe else None
    ref_seviye = "—"
    ref_fark = None
    ref_seks_karne = []
    if ref:
        ref_iyi, ref_orta, ref_zayif = ref["ort_hiz_ms"]
        if ort_hiz >= ref_iyi:
            ref_seviye = "🟢 İYİ"
        elif ort_hiz >= ref_orta:
            ref_seviye = "🟡 ORTA"
        else:
            ref_seviye = "🔴 ZAYIF"
        ref_fark = round(ort_hiz - ref_orta, 2)

        # Her seksiyonu referansa kıyasla
        ref_seks = ref.get("seksiyonlar", [])
        for i, sek in enumerate(seksiyonlar):
            if i < len(ref_seks):
                r_hiz = ref_seks[i][2]
                fark = round(sek["hiz_ms"] - r_hiz, 2)
                durum = "+" if fark > 0.2 else ("-" if fark < -0.2 else "=")
                ref_seks_karne.append({
                    "bolum": f"{sek['baslangic']}-{sek['bitis']}m",
                    "gercek": sek["hiz_ms"],
                    "referans": r_hiz,
                    "fark": fark,
                    "durum": durum,
                })

    return {
        "at": at_adi,
        "kosu_no": kosu_no,
        "sira": at_data.get("sira", ""),
        "derece": at_data.get("derece", ""),
        "jokey": at_data.get("jokey", ""),
        "kilo": at_data.get("kilo", ""),
        "seksiyonlar": seksiyonlar,
        "hizlar": hizlar,
        "ort_hiz": round(ort_hiz, 2),
        "max_hiz": round(max_hiz, 2),
        "min_hiz": round(min_hiz, 2),
        "erken_pace": round(early, 2),
        "gec_pace": round(late, 2),
        "pace_fark": round(pace_diff, 2),
        "tempo_profil": tempo_profil,
        "son_200_hiz": son_200,
        "son_400_hiz": son_400,
        "tempo_skor": skor,
        "poz_degisim": poz_degisim,
        "pozisyonlar": pozlar,
        "kaynak": kaynak,
        "kosu_mesafe": kosu_mesafe,
        "kosu_pist": kosu_pist,
        "ref_seviye": ref_seviye,
        "ref_fark": ref_fark,
        "ref_seks_karne": ref_seks_karne,
    }


# ─── Analiz ───────────────────────────────────────────────

def galop_to_sec(t: str) -> float | None:
    if not t or str(t).strip() in ("","-","Kenter","ÇR","R"): return None
    t = str(t).strip().replace(",",".")
    parts = t.split(".")
    try:
        if len(parts) == 3: return int(parts[0])*60 + int(parts[1]) + int(parts[2])/10
        elif len(parts) == 2: return float(t)
    except: pass
    return None

def derece_to_sec(t: str) -> float | None:
    if not t or t in ("-","0"): return None
    t = re.sub(r"[^\d.]","",str(t))
    parts = t.split(".")
    try:
        if len(parts)==3: return int(parts[0])*60+int(parts[1])+int(parts[2])/100
        elif len(parts)==2: return float(t)
    except: pass
    return None

def sec_fmt(s: float | None) -> str:
    if s is None: return "—"
    if s >= 60: m=int(s)//60; return f"{m}:{s-m*60:05.2f}"
    return f"{s:.2f}"


def analiz_galop(galop_rows: list, n: int = 4) -> dict:
    """At bazında son N galop analizi — tüm mesafe dereceleri + trend."""
    if not galop_rows: return {}
    df = pd.DataFrame(galop_rows)
    df["_date"] = df["g_tarih"].apply(parse_date_key)

    mesafe_cols = ["400","600","800","1000","1200","1400"]
    for col in mesafe_cols:
        if col in df.columns:
            df[f"_{col}s"] = df[col].apply(galop_to_sec)

    result = {}
    for at, grp in df.groupby("at"):
        grp   = grp.sort_values("_date", ascending=False)
        son_n = grp.head(n)
        vals_400 = son_n["_400s"].dropna() if "_400s" in son_n.columns else pd.Series()

        # Tüm mesafe dereceleri
        mesafe_analiz = {}
        for col in mesafe_cols:
            scol = f"_{col}s"
            if scol in son_n.columns:
                vals = son_n[scol].dropna()
                if not vals.empty:
                    mesafe_analiz[col] = {
                        "en_iyi": round(vals.min(), 2),
                        "ort":    round(vals.mean(), 2),
                        "son":    round(vals.iloc[0], 2) if len(vals) > 0 else None,
                        "sayi":   len(vals),
                    }

        # 400m galop trend tespiti (son 3+ galop)
        galop_trend = "—"
        galop_trend_skor = 0.0
        if "_400s" in grp.columns:
            trend_vals = grp["_400s"].dropna().head(5).tolist()
            if len(trend_vals) >= 3:
                son = sum(trend_vals[:2]) / 2
                eski = sum(trend_vals[-2:]) / 2
                galop_trend_skor = round(eski - son, 2)  # pozitif = iyileşme
                if galop_trend_skor > 0.3:
                    galop_trend = "🟢 HIZLANIYOR"
                elif galop_trend_skor < -0.3:
                    galop_trend = "🔴 YAVAŞLIYOR"
                else:
                    galop_trend = "🟡 STABİL"

        # Galop yoğunluğu (son kaç günde kaç galop)
        toplam_galop = len(grp)
        gun_fark = gun_farki(grp["g_tarih"].iloc[0])
        galop_yogunluk = "—"
        if gun_fark is not None and gun_fark <= 7 and toplam_galop >= 3:
            galop_yogunluk = "🔥 YOĞUN"
        elif gun_fark is not None and gun_fark <= 14 and toplam_galop >= 2:
            galop_yogunluk = "🟢 AKTİF"
        elif gun_fark is not None and gun_fark <= 21:
            galop_yogunluk = "🟡 NORMAL"
        elif gun_fark is not None:
            galop_yogunluk = "⚫ SOĞUK"

        # Pist ve şehir bazlı galop
        pist_galop = {}
        sehir_galop = {}
        for _, row in son_n.iterrows():
            p = str(row.get("pist", "")).strip()
            s = str(row.get("g_sehir", "")).strip()
            if p:
                pist_galop[p] = pist_galop.get(p, 0) + 1
            if s:
                sehir_galop[s] = sehir_galop.get(s, 0) + 1

        result[at] = {
            "at":            at,
            "galop_sayisi":  toplam_galop,
            "son_n":         n,
            "en_iyi_400":    round(vals_400.min(), 2) if not vals_400.empty else None,
            "ort_400":       round(vals_400.mean(), 2) if not vals_400.empty else None,
            "son_tarih":     grp["g_tarih"].iloc[0],
            "gun_fark":      gun_fark,
            "rows":          son_n.to_dict("records"),
            "mesafe_analiz": mesafe_analiz,
            "galop_trend":   galop_trend,
            "galop_trend_skor": galop_trend_skor,
            "galop_yogunluk": galop_yogunluk,
            "pist_galop":    pist_galop,
            "sehir_galop":   sehir_galop,
        }
    return result


def analiz_stil(profil: dict, kosu_mesafe: int = 0, kosu_pist: str = "",
                trakus_data: dict = None) -> dict:
    """
    Koşu stili analizi — Trakus pozisyon verisine dayalı gerçek stil tespiti.

    trakus_data: tempo_an'dan gelen at verisi (pozisyonlar, seksiyonlar)
    Öncelik: Trakus pozisyon → geçmiş sıra/hız verisi (fallback)
    """
    races = profil.get("races", [])
    if not races:
        return {"stil": "❓ Veri Yok", "stil_skor": 0, "stil_detay": "",
                "mesafe_pref": "—", "kazanma_oran": 0, "tutarlilik": "—",
                "form_notu": "—"}

    races = sorted(races, key=lambda r: parse_date_key(r.get("tarih","")), reverse=True)

    siralar, hizlar = [], []
    mesafeler, pistler = [], []
    dereceler, jokeyler = [], []
    for r in races:
        try:
            s = int(re.sub(r"[^\d]","",r.get("sira","") or ""))
            if 0 < s <= 30: siralar.append(s)
        except: pass
        m = re.search(r"\(?([+-]?\d+)\)?", str(r.get("hiz","") or ""))
        if m:
            try: hizlar.append(int(m.group(1)))
            except: pass
        try:
            msf = int(re.sub(r"[^\d]","",str(r.get("msf","") or "")))
            if msf > 0: mesafeler.append(msf)
        except: pass
        pist = str(r.get("pist","")).strip()
        if pist: pistler.append(pist)
        d = derece_to_sec(r.get("derece",""))
        if d: dereceler.append(d)
        j = str(r.get("jokey","")).strip()
        if j: jokeyler.append(j)

    ort_s = round(sum(siralar)/len(siralar),1) if siralar else 99
    ort_h = round(sum(hizlar)/len(hizlar),1)   if hizlar  else 0
    ilk3  = round(sum(1 for s in siralar if s<=3)/len(siralar)*100,1) if siralar else 0
    kazanma = round(sum(1 for s in siralar if s==1)/len(siralar)*100,1) if siralar else 0
    son5_s = siralar[:5]
    son3_s = siralar[:3]
    ort_son3_s = sum(son3_s)/len(son3_s) if son3_s else 99

    # ══════════════════════════════════════════════════════
    # TRAKUS POZİSYON VERİSİNDEN STİL TESPİTİ
    # ══════════════════════════════════════════════════════
    stil = ""
    stil_detay = ""
    pozisyon_profili = {}  # {erken_poz, orta_poz, son_poz, bitis_sira}

    if trakus_data and trakus_data.get("pozisyonlar"):
        pozlar = trakus_data["pozisyonlar"]
        poz_sorted = [(d, pozlar[d]) for d in sorted(pozlar.keys())]

        if len(poz_sorted) >= 2:
            # İlk %33 mesafe pozisyonları
            n_sek = len(poz_sorted)
            erken_n = max(1, n_sek // 3)
            orta_n = max(1, n_sek // 3)
            erken_pozlar = [p for _, p in poz_sorted[:erken_n]]
            orta_pozlar = [p for _, p in poz_sorted[erken_n:erken_n+orta_n]]
            son_pozlar = [p for _, p in poz_sorted[-erken_n:]]
            bitis_sira = poz_sorted[-1][1]

            ort_erken = sum(erken_pozlar) / len(erken_pozlar)
            ort_son = sum(son_pozlar) / len(son_pozlar)

            pozisyon_profili = {
                "erken_poz": round(ort_erken, 1),
                "orta_poz": round(sum(orta_pozlar)/len(orta_pozlar), 1) if orta_pozlar else None,
                "son_poz": round(ort_son, 1),
                "bitis_sira": bitis_sira,
                "poz_degisim": round(ort_erken - ort_son, 1),  # + = öne geldi
            }

            # TRAKUS bazlı stil sınıflandırma
            if ort_erken <= 2.0 and ort_son <= 3.0:
                stil = "🟢 ÖNDE GİDER (Lider)"
                stil_detay = (f"Trakus: Erken poz {ort_erken:.1f} → Son poz {ort_son:.1f}. "
                              f"Baştan sona önde koşuyor. Kaçak yarışlarda avantajlı.")
            elif ort_erken <= 3.0 and ort_son <= 4.0:
                stil = "🟢 ÖNDEN TAKİP"
                stil_detay = (f"Trakus: Erken {ort_erken:.1f} → Son {ort_son:.1f}. "
                              f"Liderin hemen arkasından takip. Açık pistte güçlü.")
            elif ort_erken - ort_son >= 2.0:
                stil = "🔵 GERİDEN ATAĞI"
                stil_detay = (f"Trakus: Erken {ort_erken:.1f} → Son {ort_son:.1f} "
                              f"({ort_erken - ort_son:+.1f} ilerleme). "
                              f"Geride başlayıp son bölümde öne çıkıyor.")
            elif ort_erken - ort_son >= 1.0:
                stil = "🔵 KAPANIŞÇI"
                stil_detay = (f"Trakus: Erken {ort_erken:.1f} → Son {ort_son:.1f} "
                              f"({ort_erken - ort_son:+.1f}). "
                              f"Yavaş başlayıp güçlü bitiriyor. Tempolu yarışta avantaj.")
            elif abs(ort_erken - ort_son) < 1.0 and ort_erken <= 5.0:
                stil = "🟡 ORTADAN KOŞUCU"
                stil_detay = (f"Trakus: Erken {ort_erken:.1f} → Son {ort_son:.1f}. "
                              f"Sabit pozisyonda koşuyor, grubun ortasında.")
            elif ort_son > ort_erken + 1.0:
                stil = "🔴 ERKEN YORULAN"
                stil_detay = (f"Trakus: Erken {ort_erken:.1f} → Son {ort_son:.1f} "
                              f"({ort_erken - ort_son:.1f} düşüş). "
                              f"Öne çıkıp geriliyor. Kısa mesafede daha uygun.")
            else:
                stil = "🟡 BELİRSİZ STİL"
                stil_detay = (f"Trakus: Erken {ort_erken:.1f} → Son {ort_son:.1f}. "
                              f"Net bir koşu stili tespit edilemedi.")

    # Fallback: Trakus verisi yoksa profil verisinden tahmin
    if not stil:
        son3_h = hizlar[:3] if hizlar else []
        ort_son3_h = sum(son3_h)/len(son3_h) if son3_h else 0
        if ort_s <= 2.5 and kazanma >= 25:
            stil = "🟢 ÖNDE GİDER (tahmin)"
            stil_detay = "Profil: Ort sıra çok düşük, kazanma oranı yüksek → önde koşma eğilimi"
        elif ort_s <= 3.5:
            stil = "🟢 ÖNDEN TAKİP (tahmin)"
            stil_detay = "Profil: Sürekli ilk sıralarda → önden koşma eğilimi"
        elif ort_s <= 5.5 and ort_son3_s < ort_s:
            stil = "🟡 YÜKSELİCİ (tahmin)"
            stil_detay = "Profil: Son koşularda sıra yükseliyor"
        elif ort_son3_h > 25 and ilk3 > 20:
            stil = "🔵 KAPANIŞÇI (tahmin)"
            stil_detay = "Profil: Yüksek hız farkı → son bölümde atak yapıyor"
        elif ort_s <= 6.0:
            stil = "🟡 ORTADAN (tahmin)"
            stil_detay = "Profil: Orta sıralarda koşuyor"
        else:
            stil = "🔵 GERİDE (tahmin)"
            stil_detay = "Profil: Genel sıra ortalaması yüksek → geride koşma eğilimi"

    # ── Mesafe tercihi ─────────────────────────────────
    from collections import Counter
    mesafe_pref = "—"
    mesafe_detay = {}
    if mesafeler:
        mc = Counter()
        msf_siralar = {}  # mesafe grubu → sıra listesi
        for i, msf in enumerate(mesafeler):
            if msf <= 1200:   grp_name = "Sprint (≤1200m)"
            elif msf <= 1600: grp_name = "Orta (1300-1600m)"
            elif msf <= 2000: grp_name = "Klasik (1700-2000m)"
            else:             grp_name = "Uzun (2000m+)"
            mc[grp_name] += 1
            if i < len(siralar):
                msf_siralar.setdefault(grp_name, []).append(siralar[i])
        best_msf = mc.most_common(1)[0]
        mesafe_pref = f"{best_msf[0]} ({best_msf[1]} koşu)"

        # Her mesafe grubundaki ortalama sıra
        for grp_name, slist in msf_siralar.items():
            ort = round(sum(slist) / len(slist), 1)
            ilk3_g = sum(1 for s in slist if s <= 3)
            mesafe_detay[grp_name] = {
                "kosu": len(slist), "ort_sira": ort,
                "ilk3": ilk3_g,
                "kazanma": sum(1 for s in slist if s == 1),
            }

    # ── Mesafe uyumu (bugünkü koşu mesafesiyle) ─────────
    mesafe_uyumu = "—"
    mesafe_uyum_skor = 0
    if kosu_mesafe and mesafeler:
        # Bu mesafe aralığındaki geçmiş performans
        benzer = [(siralar[i] if i < len(siralar) else 99)
                  for i, msf in enumerate(mesafeler)
                  if abs(msf - kosu_mesafe) <= 200]
        if benzer:
            ort_benzer = sum(benzer) / len(benzer)
            ilk3_benzer = sum(1 for s in benzer if s <= 3) / len(benzer) * 100
            if ilk3_benzer >= 50:
                mesafe_uyumu = f"🟢 ÇOK İYİ ({len(benzer)} koşu, ort:{ort_benzer:.1f})"
                mesafe_uyum_skor = 3
            elif ilk3_benzer >= 25:
                mesafe_uyumu = f"🟡 İYİ ({len(benzer)} koşu, ort:{ort_benzer:.1f})"
                mesafe_uyum_skor = 2
            elif ort_benzer <= 5:
                mesafe_uyumu = f"🟡 ORTA ({len(benzer)} koşu, ort:{ort_benzer:.1f})"
                mesafe_uyum_skor = 1
            else:
                mesafe_uyumu = f"🔴 ZAYIF ({len(benzer)} koşu, ort:{ort_benzer:.1f})"
                mesafe_uyum_skor = 0
        else:
            mesafe_uyumu = "⚫ DENEYİMSİZ (bu mesafede koşu yok)"

    # ── Pist uyumu (bugünkü piste göre) ─────────────────
    pist_uyumu = "—"
    pist_uyum_skor = 0
    if kosu_pist and pistler:
        pist_benzer = [(siralar[i] if i < len(siralar) else 99)
                       for i, p in enumerate(pistler) if p == kosu_pist]
        if pist_benzer:
            ort_p = sum(pist_benzer) / len(pist_benzer)
            ilk3_p = sum(1 for s in pist_benzer if s <= 3) / len(pist_benzer) * 100
            if ilk3_p >= 40:
                pist_uyumu = f"🟢 GÜÇLÜ ({len(pist_benzer)} koşu, %{ilk3_p:.0f} ilk3)"
                pist_uyum_skor = 2
            elif ort_p <= 5:
                pist_uyumu = f"🟡 NORMAL ({len(pist_benzer)} koşu, ort:{ort_p:.1f})"
                pist_uyum_skor = 1
            else:
                pist_uyumu = f"🔴 ZAYIF ({len(pist_benzer)} koşu, ort:{ort_p:.1f})"
        else:
            pist_uyumu = "⚫ DENEYİMSİZ"

    # ── Jokey analizi ──────────────────────────────────
    jokey_istatistik = {}
    if jokeyler:
        jc = Counter(jokeyler)
        for jokey, sayi in jc.most_common(5):
            j_siralar = [siralar[i] for i, j in enumerate(jokeyler)
                         if j == jokey and i < len(siralar)]
            if j_siralar:
                jokey_istatistik[jokey] = {
                    "kosu": sayi,
                    "ort_sira": round(sum(j_siralar) / len(j_siralar), 1),
                    "kazanma": sum(1 for s in j_siralar if s == 1),
                    "ilk3": sum(1 for s in j_siralar if s <= 3),
                }

    # ── Tutarlılık analizi ─────────────────────────────
    tutarlilik = "—"
    tutarlilik_skor = 0
    if len(siralar) >= 4:
        std = (sum((s - ort_s)**2 for s in siralar) / len(siralar)) ** 0.5
        if std <= 1.5:
            tutarlilik = "🟢 ÇOK TUTARLI"
            tutarlilik_skor = 3
        elif std <= 2.5:
            tutarlilik = "🟡 TUTARLI"
            tutarlilik_skor = 2
        elif std <= 4.0:
            tutarlilik = "🟠 DALGALI"
            tutarlilik_skor = 1
        else:
            tutarlilik = "🔴 TUTARSIZ"

    # ── Form notu (son 3 koşu) ─────────────────────────
    if len(son3_s) >= 2:
        if all(s <= 3 for s in son3_s):      form_notu = "🔥 ZİRVEDE"
        elif ort_son3_s <= 3.0:               form_notu = "🟢 FORMDA"
        elif ort_son3_s < ort_s:              form_notu = "📈 YÜKSELİYOR"
        elif ort_son3_s > ort_s + 2:          form_notu = "📉 DÜŞÜŞTE"
        else:                                  form_notu = "🟡 NORMAL"
    else:
        form_notu = "—"

    # ── Geçmiş yarış derinlik analizi ───────────────────
    # Son 10 koşudan detaylı özet
    son10_ozet = []
    for r in races[:10]:
        try:
            sira_r = int(re.sub(r"[^\d]", "", r.get("sira", "") or ""))
        except (ValueError, TypeError):
            sira_r = None
        d_sec = derece_to_sec(r.get("derece", ""))
        try:
            msf_r = int(re.sub(r"[^\d]", "", str(r.get("msf", "") or "")))
        except (ValueError, TypeError):
            msf_r = 0
        hiz_ms = round(msf_r / d_sec, 2) if d_sec and msf_r else None
        son10_ozet.append({
            "tarih": r.get("tarih", ""),
            "sehir": r.get("sehir", ""),
            "mesafe": msf_r,
            "pist": r.get("pist", ""),
            "sira": sira_r,
            "derece": r.get("derece", ""),
            "hiz_ms": hiz_ms,
            "jokey": r.get("jokey", ""),
            "fark": r.get("fark", ""),
        })

    # ── Stil skoru (genel güç puanı) ──────────────────
    stil_skor = 0
    stil_skor += min(30, kazanma * 0.5)             # Kazanma oranı
    stil_skor += min(20, ilk3 * 0.25)               # İlk 3 oranı
    stil_skor += min(15, tutarlilik_skor * 5)        # Tutarlılık
    stil_skor += min(10, mesafe_uyum_skor * 3.3)     # Mesafe uyumu
    stil_skor += min(10, pist_uyum_skor * 5)          # Pist uyumu
    if form_notu in ("🔥 ZİRVEDE", "🟢 FORMDA"):
        stil_skor += 15
    elif form_notu == "📈 YÜKSELİYOR":
        stil_skor += 10
    elif form_notu == "📉 DÜŞÜŞTE":
        stil_skor -= 10
    stil_skor = round(max(0, min(100, stil_skor)), 1)

    # Pist tercihi
    ps = profil.get("pist_stats",{})
    best_pist = max(
        [(p,v) for p,v in ps.items() if p!="Toplam" and v.get("kosu",0)>=2],
        key=lambda x: x[1].get("hiz",0), default=(None,{})
    )
    pist_pref = ""
    if best_pist[0]:
        v = best_pist[1]
        pist_pref = f"{best_pist[0]} ({v.get('kosu',0)} koşu, hız={v.get('hiz',0)})"

    # Pist bazlı kazanma
    pist_kazanma = {}
    for p in ["Kum","Çim","Sentetik"]:
        pv = ps.get(p,{})
        if pv.get("kosu",0) >= 1:
            pist_kazanma[p] = f"{pv.get('1',0)}/{pv.get('kosu',0)}"

    # Takı
    taki_c = {}
    for r in races:
        for t in str(r.get("taki","")).split():
            t = t.strip().upper()
            if t in TAKI_ACIKLAMA: taki_c[t] = taki_c.get(t,0)+1
    taki_str = " | ".join(
        f"{k}×{v}" for k,v in sorted(taki_c.items(),key=lambda x:-x[1])[:4]
    ) if taki_c else "—"

    son5 = "-".join(str(s) for s in siralar[:5]) if siralar else "—"

    return {
        "stil":           stil,
        "stil_skor":      stil_skor,
        "stil_detay":     stil_detay,
        "ort_sira":       ort_s,
        "ort_hiz":        ort_h,
        "ilk3_pct":       ilk3,
        "kazanma_oran":   kazanma,
        "son5":           son5,
        "pist_pref":      pist_pref,
        "pist_kazanma":   pist_kazanma,
        "mesafe_pref":    mesafe_pref,
        "mesafe_detay":   mesafe_detay,
        "mesafe_uyumu":   mesafe_uyumu,
        "mesafe_uyum_skor": mesafe_uyum_skor,
        "pist_uyumu":     pist_uyumu,
        "pist_uyum_skor": pist_uyum_skor,
        "jokey_istatistik": jokey_istatistik,
        "tutarlilik":     tutarlilik,
        "tutarlilik_skor": tutarlilik_skor,
        "form_notu":      form_notu,
        "taki":           taki_str,
        "toplam_kosu":    len(siralar),
        "son10_ozet":     son10_ozet,
        "pozisyon_profili": pozisyon_profili,
    }


def analiz_perform(profil: dict, n: int = 8) -> dict:
    """Gelişmiş performans trendi — tüm yarışları tarayarak hız, derece, mesafe analizi."""
    all_races = sorted(profil.get("races", []),
                       key=lambda r: parse_date_key(r.get("tarih", "")), reverse=True)
    races = all_races[:n]
    hizlar = []
    hiz_detay = []  # [{tarih, mesafe, pist, hiz_ms, derece, sira}]
    for r in all_races:  # Tüm yarışları tara
        d = derece_to_sec(r.get("derece", ""))
        try:
            msf = int(re.sub(r"[^\d]", "", str(r.get("msf", "") or "")))
            h = msf / d if d and d > 0 else None
        except (ValueError, TypeError):
            h = None
            msf = 0
        try:
            sira = int(re.sub(r"[^\d]", "", r.get("sira", "") or ""))
        except (ValueError, TypeError):
            sira = None
        if h:
            hiz_detay.append({
                "tarih": r.get("tarih", ""),
                "mesafe": msf, "pist": r.get("pist", ""),
                "hiz_ms": round(h, 3), "derece": r.get("derece", ""),
                "sira": sira, "jokey": r.get("jokey", ""),
            })
    # Son N koşu hızları
    hizlar = [hd["hiz_ms"] for hd in hiz_detay[:n]]

    trend_skor = 0.0
    if len(hizlar) >= 2:
        trend_skor = round(hizlar[0] - hizlar[-1], 3)

    if trend_skor > 0.15:    trend = "🟢 YÜKSELİYOR"
    elif trend_skor < -0.15: trend = "🔴 DÜŞÜYOR"
    else:                    trend = "🟡 STABİL"

    # ── Mesafe bazlı en iyi hızlar ──
    from collections import defaultdict
    msf_hizlar = defaultdict(list)
    for hd in hiz_detay:
        msf = hd["mesafe"]
        if msf <= 1200:    msf_hizlar["Sprint"].append(hd["hiz_ms"])
        elif msf <= 1600:  msf_hizlar["Orta"].append(hd["hiz_ms"])
        elif msf <= 2000:  msf_hizlar["Klasik"].append(hd["hiz_ms"])
        else:              msf_hizlar["Uzun"].append(hd["hiz_ms"])

    mesafe_en_iyi = {}
    for grp, vals in msf_hizlar.items():
        mesafe_en_iyi[grp] = {
            "en_iyi": round(max(vals), 3),
            "ort": round(sum(vals) / len(vals), 3),
            "sayi": len(vals),
        }

    # ── Pist bazlı performans ──
    pist_hizlar = defaultdict(list)
    for hd in hiz_detay:
        p = hd.get("pist", "").strip()
        if p:
            pist_hizlar[p].append(hd["hiz_ms"])
    pist_perform = {}
    for p, vals in pist_hizlar.items():
        pist_perform[p] = {
            "en_iyi": round(max(vals), 3),
            "ort": round(sum(vals) / len(vals), 3),
            "sayi": len(vals),
        }

    # ── Kazandığı koşulardaki hız profili ──
    kazandigi = [hd for hd in hiz_detay if hd.get("sira") == 1]
    kazanma_hiz = None
    if kazandigi:
        kazanma_hiz = round(sum(hd["hiz_ms"] for hd in kazandigi) / len(kazandigi), 3)

    # ── Son 3 koşu momentum (hız değişim ivmesi) ──
    momentum = "—"
    if len(hizlar) >= 3:
        delta1 = hizlar[0] - hizlar[1]  # son → önceki
        delta2 = hizlar[1] - hizlar[2]  # önceki → daha önceki
        ivme = delta1 - delta2
        if ivme > 0.1:
            momentum = "🚀 İVMELENİYOR"
        elif ivme < -0.1:
            momentum = "📉 İVME KAYBI"
        else:
            momentum = "➡️ SABİT İVME"

    return {
        "trend":          trend,
        "trend_skor":     trend_skor,
        "en_iyi_hiz":     round(max(hizlar), 3) if hizlar else None,
        "ort_hiz_ms":     round(sum(hizlar) / len(hizlar), 3) if hizlar else None,
        "hiz_detay":      hiz_detay[:n],
        "mesafe_en_iyi":  mesafe_en_iyi,
        "pist_perform":   pist_perform,
        "kazanma_hiz":    kazanma_hiz,
        "momentum":       momentum,
        "toplam_yaris":   len(hiz_detay),
    }


def analiz_genel_yaris(atlar: list, galop_an: dict, stiller: dict,
                       performlar: dict, tempo_an: dict,
                       kosu_mesafe: int = 0, kosu_pist: str = "") -> list:
    """
    Tüm veri kaynaklarını birleştiren kapsamlı yarış analizi.
    Her at için birleşik güç puanı, detaylı yorum ve tahmin üretir.
    """
    ref = mesafe_tempo_bilgisi(kosu_mesafe, kosu_pist) if kosu_mesafe else None
    sonuclar = []

    for at in atlar:
        adi = at.get("at", "")
        g = galop_an.get(adi, {})
        s = stiller.get(adi, {})
        p = performlar.get(adi, {})
        t = tempo_an.get(adi, {})

        # ── 1. Galop Puanı (max 25) ──
        galop_puan = 0.0
        if g.get("en_iyi_400"):
            galop_puan += max(0, min(15, (27 - g["en_iyi_400"]) * 3))
        if g.get("galop_trend_skor"):
            galop_puan += min(5, g["galop_trend_skor"] * 5)
        if g.get("galop_yogunluk") in ("🔥 YOĞUN", "🟢 AKTİF"):
            galop_puan += 5
        galop_puan = min(25, galop_puan)

        # ── 2. Form/Stil Puanı (max 25) ──
        stil_puan = 0.0
        stil_puan += min(10, s.get("kazanma_oran", 0) * 0.2)
        stil_puan += min(8, s.get("ilk3_pct", 0) * 0.1)
        if s.get("form_notu") in ("🔥 ZİRVEDE", "🟢 FORMDA"):
            stil_puan += 7
        elif s.get("form_notu") == "📈 YÜKSELİYOR":
            stil_puan += 4
        elif s.get("form_notu") == "📉 DÜŞÜŞTE":
            stil_puan -= 3
        stil_puan = max(0, min(25, stil_puan))

        # ── 3. Mesafe/Pist Uyum Puanı (max 20) ──
        uyum_puan = 0.0
        uyum_puan += min(12, s.get("mesafe_uyum_skor", 0) * 4)
        uyum_puan += min(8, s.get("pist_uyum_skor", 0) * 4)
        uyum_puan = min(20, uyum_puan)

        # ── 4. Performans Trend Puanı (max 15) ──
        trend_puan = 0.0
        if p.get("trend_skor"):
            trend_puan += min(8, p["trend_skor"] * 20)
        if p.get("momentum") == "🚀 İVMELENİYOR":
            trend_puan += 5
        elif p.get("momentum") == "📉 İVME KAYBI":
            trend_puan -= 3
        # Referans karşılaştırması
        if ref and p.get("ort_hiz_ms"):
            ref_orta = ref["ort_hiz_ms"][1]
            if p["ort_hiz_ms"] >= ref_orta:
                trend_puan += 2
        trend_puan = max(0, min(15, trend_puan))

        # ── 5. Tempo Puanı (max 15) ──
        tempo_puan = 0.0
        if t:
            tempo_puan += min(8, t.get("tempo_skor", 0) * 0.08)
            if t.get("ref_seviye") == "🟢 İYİ":
                tempo_puan += 4
            elif t.get("ref_seviye") == "🟡 ORTA":
                tempo_puan += 2
            if t.get("pace_fark", 0) > 0.3:
                tempo_puan += 3  # Kapanış gücü
        tempo_puan = max(0, min(15, tempo_puan))

        # ── Toplam Güç Puanı ──
        toplam = round(galop_puan + stil_puan + uyum_puan +
                       trend_puan + tempo_puan, 1)

        # ── Yorum Üretimi ──
        guclu = []
        zayif = []
        if galop_puan >= 18: guclu.append("Galop çok güçlü")
        elif galop_puan <= 8: zayif.append("Galop zayıf")
        if stil_puan >= 18: guclu.append("Form üst düzey")
        elif stil_puan <= 5: zayif.append("Form düşük")
        if uyum_puan >= 15: guclu.append("Mesafe/pist uyumlu")
        elif uyum_puan <= 5: zayif.append("Mesafe/pist uyumsuz")
        if trend_puan >= 10: guclu.append("Trend yükselen")
        elif trend_puan <= 3: zayif.append("Trend düşüşte")
        if tempo_puan >= 10: guclu.append("Tempo üstün")

        yorum = ""
        if guclu: yorum += "💪 " + ", ".join(guclu)
        if zayif: yorum += (" | " if yorum else "") + "⚠️ " + ", ".join(zayif)
        if not yorum: yorum = "Dengeli profil"

        # Tahmini sıra (basit sıralama için)
        sonuclar.append({
            "at": adi,
            "no": at.get("no", ""),
            "jokey": at.get("jokey", ""),
            "kilo": at.get("kilo", ""),
            "toplam_puan": toplam,
            "galop_puan": round(galop_puan, 1),
            "stil_puan": round(stil_puan, 1),
            "uyum_puan": round(uyum_puan, 1),
            "trend_puan": round(trend_puan, 1),
            "tempo_puan": round(tempo_puan, 1),
            "form": s.get("form_notu", "—"),
            "stil": s.get("stil", "—"),
            "mesafe_uyumu": s.get("mesafe_uyumu", "—"),
            "pist_uyumu": s.get("pist_uyumu", "—"),
            "trend": p.get("trend", "—"),
            "momentum": p.get("momentum", "—"),
            "galop_trend": g.get("galop_trend", "—"),
            "tutarlilik": s.get("tutarlilik", "—"),
            "yorum": yorum,
        })

    sonuclar.sort(key=lambda x: x["toplam_puan"], reverse=True)

    # Tahmini sıra ata
    for i, s in enumerate(sonuclar):
        s["tahmin_sira"] = i + 1

    return sonuclar


# ─── Ana Uygulama ─────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🏇  At Yarışı Pro Analiz  v15.0")
        self.geometry("1700x960")
        self.minsize(1200,720)
        self.configure(bg=BG)

        # State
        self.bulten     = None    # scrape_bulten sonucu
        self.sel_kosu   = None    # seçili koşu dict
        self.galoplar   = []      # scrape_galoplar sonucu
        self.galop_an   = {}      # analiz_galop sonucu
        self.profiller  = {}      # {at: scrape_profil}
        self.stiller    = {}      # {at: analiz_stil}
        self.performlar = {}      # {at: analiz_perform}
        self.tjk_trakus = []      # scrape_tjk_sonuclar sonucu
        self.tempo_an   = {}      # analiz_tempo sonucu
        self.genel_yaris_sonuc = []  # analiz_genel_yaris sonucu
        self._ready     = False

        self._build_ui()
        threading.Thread(target=self._setup, daemon=True).start()

    # ── Setup ─────────────────────────────────────────────

    def _setup(self):
        global _tess, _pop
        self._st("Sistem kontrol ediliyor…")
        p = ensure_pop(self._st)
        if p is not None: _pop = p or None
        t = ensure_tess(self._st)
        if t: _tess = t
        ensure_bs4(self._st)
        self._ready = True
        self._st("Hazır  —  Tarih ve şehir seçip Bülten Çek butonuna basın.")

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        self._style()
        self._topbar()
        self._toolbar()
        self._main_area()
        self._statusbar()

    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure("Treeview", background=PANEL, foreground=TEXT,
                    fieldbackground=PANEL, rowheight=24, font=F_N, borderwidth=0)
        s.configure("Treeview.Heading", background=CARD, foreground=TEXT,
                    font=F_S, relief="flat")
        s.map("Treeview",
              background=[("selected","#1A4A8A")],
              foreground=[("selected",TEXT)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=DIM,
                    font=F_S, padding=(12,6))
        s.map("TNotebook.Tab",
              background=[("selected",ACCENT)],
              foreground=[("selected",TEXT)])
        s.configure("Horizontal.TProgressbar",
                    background=ACCENT, troughcolor=PANEL)

    def _topbar(self):
        tb = tk.Frame(self, bg="#0A1520", height=48)
        tb.pack(fill="x"); tb.pack_propagate(False)
        tk.Label(tb, text="🏇  AT YARIŞI PRO ANALİZ",
                 font=("Segoe UI",14,"bold"), bg="#0A1520", fg=GOLD).pack(side="left", padx=16)
        tk.Label(tb, text="Yenibeygir  •  TJK  •  Accurace",
                 font=F_XS, bg="#0A1520", fg=DIM).pack(side="left", padx=8)
        # Saat
        self.clock_var = tk.StringVar()
        tk.Label(tb, textvariable=self.clock_var,
                 font=F_N, bg="#0A1520", fg=DIM).pack(side="right", padx=16)
        self._tick()

    def _tick(self):
        self.clock_var.set(datetime.now().strftime("%d.%m.%Y  %H:%M:%S"))
        self.after(1000, self._tick)

    def _toolbar(self):
        bar = tk.Frame(self, bg=CARD, height=46)
        bar.pack(fill="x"); bar.pack_propagate(False)

        def lbl(t):
            tk.Label(bar, text=t, font=F_XS, bg=CARD, fg=DIM).pack(side="left", padx=(12,2))

        def entry(w=12, default=""):
            e = tk.Entry(bar, bg=BG, fg=TEXT, insertbackground=TEXT,
                         font=F_N, relief="flat", width=w,
                         highlightthickness=1, highlightbackground=BORDER)
            if default: e.insert(0, default)
            e.pack(side="left", padx=(0,6), ipady=4)
            return e

        def btn(t, cmd, bg=ACCENT, w=None):
            kw = {"width": w} if w else {}
            b = tk.Button(bar, text=t, command=cmd, bg=bg, fg=TEXT,
                          font=F_S, relief="flat", cursor="hand2",
                          activebackground=bg, activeforeground=TEXT,
                          padx=10, pady=6, **kw)
            b.pack(side="left", padx=3)
            return b

        lbl("Tarih:")
        self.e_tarih = entry(12, bugun())

        lbl("Şehir:")
        self.sehir_var = tk.StringVar(value="istanbul")
        cb = ttk.Combobox(bar, textvariable=self.sehir_var,
                          values=SEHIRLER, state="readonly",
                          font=F_N, width=12)
        cb.pack(side="left", padx=(0,6))

        btn("📥  BÜLTENİ ÇEK", self.cek_bulten, bg="#1A5276")

        # Önceki / Sonraki gün
        btn("◀", self._onceki_gun, bg="#243040", w=3)
        btn("▶", self._sonraki_gun, bg="#243040", w=3)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)

        lbl("Koşu:")
        self.kosu_var = tk.StringVar()
        self.kosu_cb  = ttk.Combobox(bar, textvariable=self.kosu_var,
                                      state="readonly", font=F_N, width=40)
        self.kosu_cb.pack(side="left", padx=(0,6))
        self.kosu_cb.bind("<<ComboboxSelected>>", lambda e: self._sec_kosu())

        btn("🐎  KOŞUYU ANALİZ ET", self.analiz_kosu, bg="#1A5C2A")

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)

        self.prog = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.prog.pack(side="left", padx=4)

        tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
        btn("📡 TJK Trakus", self._cek_tjk_trakus, bg="#6C3483")

        # Export
        btn("💾 Excel", self.export_excel, bg="#145A32")
        btn("📄 CSV",   self.export_csv,   bg="#1A4F6E")

    def _main_area(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=6, pady=4)

        # Sol: koşu atları listesi (250px)
        self._build_left(main)

        # Sağ: sekmeler
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_tabs(right)

    def _statusbar(self):
        self.st_var = tk.StringVar(value="Hazırlanıyor…")
        bar = tk.Frame(self, bg="#0A1520", height=24)
        bar.pack(fill="x", side="bottom"); bar.pack_propagate(False)
        tk.Label(bar, textvariable=self.st_var,
                 font=F_XS, bg="#0A1520", fg=DIM).pack(side="left", padx=10)

    def _build_left(self, parent):
        lf = tk.Frame(parent, bg=PANEL, width=260,
                      highlightthickness=1, highlightbackground=BORDER)
        lf.pack(side="left", fill="y", padx=(0,6))
        lf.pack_propagate(False)

        tk.Label(lf, text="KOŞU ATLARI", font=F_S, bg=PANEL, fg=DIM
                 ).pack(anchor="w", padx=8, pady=(8,4))

        # Koşu özet kartı
        self.kosu_info = tk.Label(lf, text="—", font=F_XS,
                                   bg=CARD, fg=GOLD, wraplength=240,
                                   justify="left", padx=8, pady=6)
        self.kosu_info.pack(fill="x", padx=6, pady=(0,4))

        # At listesi
        lf2 = tk.Frame(lf, bg=BG,
                        highlightthickness=1, highlightbackground=BORDER)
        lf2.pack(fill="both", expand=True, padx=6, pady=(0,4))

        vsb = ttk.Scrollbar(lf2, orient="vertical")
        self.at_tree = ttk.Treeview(lf2, columns=("no","at","agf","son10","hnd","taki"),
                                     show="headings", yscrollcommand=vsb.set,
                                     selectmode="browse")
        vsb.config(command=self.at_tree.yview)
        vsb.pack(side="right", fill="y")
        self.at_tree.pack(fill="both", expand=True)

        for col, w, txt in [
            ("no",   30, "#"),
            ("at",  120, "At Adı"),
            ("agf",  35, "AGF"),
            ("son10",80, "Son 10"),
            ("hnd",  35, "Hnd"),
            ("taki", 60, "Takı"),
        ]:
            self.at_tree.heading(col, text=txt)
            self.at_tree.column(col, width=w, anchor="center", minwidth=w)

        self.at_tree.tag_configure("good", background="#1A3020", foreground=GREEN)
        self.at_tree.tag_configure("mid",  background="#2A2A10", foreground=YELLOW)
        self.at_tree.tag_configure("odd",  background="#162030")
        self.at_tree.tag_configure("ev",   background=PANEL)

        # Filtre
        ff = tk.Frame(lf, bg=PANEL)
        ff.pack(fill="x", padx=6, pady=(0,4))
        tk.Label(ff, text="Filtre:", font=F_XS, bg=PANEL, fg=DIM).pack(side="left")
        self.at_filter = tk.Entry(ff, bg=BG, fg=TEXT, insertbackground=TEXT,
                                   font=F_XS, relief="flat", width=14,
                                   highlightthickness=1, highlightbackground=BORDER)
        self.at_filter.pack(side="left", padx=4, ipady=2)
        self.at_filter.bind("<KeyRelease>", lambda e: self._filter_atlar())

    def _build_tabs(self, parent):
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True)

        tabs = [
            ("  📊  Genel Analiz  ",    self._build_genel_tab),
            ("  🐎  Galop Detay  ",     self._build_galop_tab),
            ("  🎨  Koşu Stili  ",      self._build_stil_tab),
            ("  📈  Performans Trendi  ",self._build_trend_tab),
            ("  📋  Yarış Sonuçları  ",  self._build_sonuc_tab),
            ("  🔄  Karşılaştırma  ",   self._build_karsi_tab),
            ("  ⚡  Son 2 Yarış Hız  ",  self._build_son2hiz_tab),
            ("  👁  Takip Atları  ",     self._build_takip_tab),
            ("  🎬  Yarış Senaryosu  ", self._build_senaryo_tab),
            ("  🏁  Trakus & Tempo  ",  self._build_trakus_tab),
            ("  🎯  Genel Yarış Analizi  ", self._build_genel_yaris_tab),
        ]
        self.tab_frames = {}
        for name, builder in tabs:
            f = tk.Frame(self.nb, bg=BG)
            self.nb.add(f, text=name)
            builder(f)
            self.tab_frames[name] = f

    # ── Tab: Genel Analiz ────────────────────────────────

    def _build_genel_tab(self, parent):
        # Koşu bilgi kartı
        self.genel_kosu_card = tk.Frame(parent, bg=CARD,
                                         highlightthickness=1,
                                         highlightbackground=BORDER)
        self.genel_kosu_card.pack(fill="x", padx=8, pady=(6, 0))
        self.genel_kosu_lbl = tk.Label(self.genel_kosu_card,
                                        text="Koşu seçilmedi",
                                        font=F_S, bg=CARD, fg=GOLD,
                                        padx=8, pady=4, justify="left")
        self.genel_kosu_lbl.pack(anchor="w")

        # Podium
        self.pod = tk.Frame(parent, bg=BG)
        self.pod.pack(fill="x", padx=8, pady=(6,4))

        tk.Label(parent, text="Tüm Atlar — Birleşik Skor (Galop + Stil + Performans + Uyum)",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", padx=8, pady=(0,4))

        self.tree_genel = self._make_tree(parent)

        # Alt: hızlı özet rapor
        bt = tk.Frame(parent, bg=BG)
        bt.pack(fill="x", padx=8, pady=(0, 6))
        self.txt_genel = tk.Text(bt, bg=PANEL, fg=TEXT, font=F_XS,
                                  height=6, relief="flat",
                                  highlightthickness=1,
                                  highlightbackground=BORDER,
                                  state="disabled", wrap="word")
        self.txt_genel.pack(fill="x", expand=True)

    # ── Tab: Galop Detay ─────────────────────────────────

    def _build_galop_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=8, pady=(6,4))
        tk.Label(top, text="At:", font=F_S, bg=BG, fg=DIM).pack(side="left")
        self.g_horse_var = tk.StringVar(value="Tümü")
        self.g_horse_cb  = ttk.Combobox(top, textvariable=self.g_horse_var,
                                         state="readonly", width=26, font=F_N)
        self.g_horse_cb.pack(side="left", padx=6)
        self.g_horse_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_galop_detail())
        tk.Label(top, text="Son N galop:", font=F_XS, bg=BG, fg=DIM).pack(side="left", padx=(12,0))
        self.g_n_var = tk.StringVar(value="4")
        ttk.Combobox(top, textvariable=self.g_n_var,
                     values=["4","5","8","10","Tümü"],
                     state="readonly", width=6, font=F_N
                     ).pack(side="left", padx=4)
        tk.Button(top, text="Göster", command=self._refresh_galop_detail,
                  bg=BLUE, fg=TEXT, font=F_S, relief="flat",
                  padx=8, pady=4).pack(side="left", padx=4)

        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        # Sol: tablo
        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        self.tree_galop = self._make_tree(lp)

        # Sağ: bar grafik
        rp = tk.Frame(mid, bg=BG, width=380)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="En İyi 400m Karşılaştırması",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_galop = tk.Canvas(rp, bg=PANEL,
                                   highlightthickness=1, highlightbackground=BORDER)
        self.cv_galop.pack(fill="both", expand=True)
        self.cv_galop.bind("<Configure>", lambda e: self._draw_galop_bar())

        # Alt: detaylı galop raporu
        bt = tk.Frame(parent, bg=BG)
        bt.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bt, text="Galop Raporu:", font=F_S, bg=BG, fg=GOLD
                 ).pack(side="left")
        self.txt_galop = tk.Text(bt, bg=PANEL, fg=TEXT, font=F_XS,
                                  height=8, relief="flat",
                                  highlightthickness=1,
                                  highlightbackground=BORDER,
                                  state="disabled", wrap="word")
        self.txt_galop.pack(fill="x", expand=True, padx=(6, 0))

    # ── Tab: Koşu Stili ──────────────────────────────────

    def _build_stil_tab(self, parent):
        self.stil_status = tk.StringVar(value="Analiz çalıştırınca otomatik dolar…")
        tk.Label(parent, textvariable=self.stil_status,
                 font=F_S, bg=BG, fg=TEAL).pack(anchor="w", padx=8, pady=(8,4))

        self.stil_cards = tk.Frame(parent, bg=BG)
        self.stil_cards.pack(fill="x", padx=8, pady=(0,6))

        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=8, pady=(0,4))
        tk.Label(top, text="At:", font=F_S, bg=BG, fg=DIM).pack(side="left")
        self.stil_horse_var = tk.StringVar(value="Tümü")
        self.stil_horse_cb  = ttk.Combobox(top, textvariable=self.stil_horse_var,
                                            state="readonly", width=28, font=F_N)
        self.stil_horse_cb.pack(side="left", padx=6)
        self.stil_horse_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_stil_detail())

        # Seçili at detay kartı
        self.stil_detay_card = tk.Frame(top, bg=CARD, padx=10, pady=4,
                                         highlightthickness=1,
                                         highlightbackground=BORDER)
        self.stil_detay_card.pack(side="left", padx=12)
        self.stil_detay_lbl = tk.Label(self.stil_detay_card, text="",
                                        font=F_XS, bg=CARD, fg=TEAL,
                                        wraplength=500, justify="left")
        self.stil_detay_lbl.pack()

        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        tk.Label(lp, text="Koşu Stili Analizi — Pro",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.tree_stil = self._make_tree(lp)

        rp = tk.Frame(mid, bg=BG, width=420)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Yarış Geçmişi",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.tree_stil_detail = self._make_tree(rp)

        # Alt: detaylı stil raporu
        bt = tk.Frame(parent, bg=BG)
        bt.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bt, text="Koşu Stili Raporu:", font=F_S, bg=BG, fg=GOLD
                 ).pack(anchor="w")
        self.txt_stil = tk.Text(bt, bg=PANEL, fg=TEXT, font=F_XS,
                                 height=10, relief="flat",
                                 highlightthickness=1,
                                 highlightbackground=BORDER,
                                 state="disabled", wrap="word")
        self.txt_stil.pack(fill="x", expand=True)

    # ── Tab: Performans Trendi ───────────────────────────

    def _build_trend_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=8, pady=(6,4))
        tk.Label(top, text="At:", font=F_S, bg=BG, fg=DIM).pack(side="left")
        self.trend_horse_var = tk.StringVar(value="Tümü")
        self.trend_horse_cb  = ttk.Combobox(top, textvariable=self.trend_horse_var,
                                             state="readonly", width=28, font=F_N)
        self.trend_horse_cb.pack(side="left", padx=6)
        self.trend_horse_cb.bind("<<ComboboxSelected>>", lambda e: self._draw_trend_chart())

        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        tk.Label(lp, text="Performans Tablosu",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.tree_trend = self._make_tree(lp)

        rp = tk.Frame(mid, bg=BG, width=450)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Hız Trend Grafiği (m/s)",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_trend = tk.Canvas(rp, bg=PANEL,
                                   highlightthickness=1, highlightbackground=BORDER)
        self.cv_trend.pack(fill="both", expand=True)
        self.cv_trend.bind("<Configure>", lambda e: self._draw_trend_chart())


    # ── Tab: Yarış Sonuçları ─────────────────────────────

    def _build_sonuc_tab(self, parent):
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(fill="x", padx=8, pady=(8,4))

        tk.Button(ctrl, text="📥  SONUÇLARI ÇEK",
                  command=self._cek_sonuclar,
                  bg="#1A5276", fg=TEXT, font=F_M, relief="flat",
                  cursor="hand2", padx=14, pady=7).pack(side="left")

        tk.Label(ctrl, text="Yıldız eşiği (hız ind.):",
                 font=F_XS, bg=BG, fg=DIM).pack(side="left", padx=(16,2))
        self.yildiz_esik_var = tk.StringVar(value="30")
        ttk.Combobox(ctrl, textvariable=self.yildiz_esik_var,
                     values=["10","20","30","40","50","60"],
                     state="readonly", width=5, font=F_N).pack(side="left", padx=4)
        tk.Button(ctrl, text="⭐ Yıldızla", command=self._yildizla,
                  bg="#7D6608", fg=TEXT, font=F_S, relief="flat",
                  cursor="hand2", padx=8, pady=5).pack(side="left", padx=4)

        self.sonuc_info = tk.StringVar(value="")
        tk.Label(ctrl, textvariable=self.sonuc_info,
                 font=F_XS, bg=BG, fg=TEAL).pack(side="left", padx=12)

        kosu_row = tk.Frame(parent, bg=BG)
        kosu_row.pack(fill="x", padx=8, pady=(0,4))
        tk.Label(kosu_row, text="Koşu:", font=F_S, bg=BG, fg=DIM).pack(side="left")
        self.sonuc_kosu_var = tk.StringVar(value="Tümü")
        self.sonuc_kosu_cb  = ttk.Combobox(kosu_row,
                                            textvariable=self.sonuc_kosu_var,
                                            state="readonly", width=50, font=F_N)
        self.sonuc_kosu_cb.pack(side="left", padx=6)
        self.sonuc_kosu_cb.bind("<<ComboboxSelected>>",
                                lambda e: self._filtrele_sonuclar())

        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        self.tree_sonuc = self._make_tree(lp)

        rp = tk.Frame(mid, bg=BG, width=380)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Hız Dagilimi (m/s)",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_sonuc = tk.Canvas(rp, bg=PANEL,
                                   highlightthickness=1, highlightbackground=BORDER)
        self.cv_sonuc.pack(fill="both", expand=True)
        self.cv_sonuc.bind("<Configure>", lambda e: self._draw_sonuc_chart())

    def _scrape_sonuclar(self, tarih, sehir):
        from bs4 import BeautifulSoup
        url  = f"https://yenibeygir.com/{tarih_url(tarih)}/{sehir_url(sehir)}/sonuclar"
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")
        tum_rows = []
        kosu_no  = 0
        kosu_meta = {}

        for elem in soup.find_all(["p","div","h2","h3","table","span"]):
            tag = elem.name
            txt = elem.get_text(" ", strip=True)

            if tag in ("p","div","span","h2","h3"):
                saat_m = re.search(r"(\d{2}:\d{2})", txt)
                msf_m  = re.search(r"(\d{3,5})\s*(Kum|Cim|Sentetik|Toprak)?", txt)
                para_m = re.search(r"[tT][lL][^\d]*(\d[\d\.\,]+)", txt)
                no_m   = re.search(r"\b(\d{1,2})\s*\.\s*(?:\d{2}:\d{2})", txt)
                if no_m and (saat_m or msf_m):
                    kosu_no = int(no_m.group(1))
                    kosu_meta[kosu_no] = {
                        "saat": saat_m.group(1) if saat_m else "",
                        "msf":  msf_m.group(1)  if msf_m  else "",
                        "pist": msf_m.group(2)  if msf_m and msf_m.group(2) else "",
                    }
                continue

            if tag == "table":
                header_txt = elem.get_text(" ")
                has_sira   = "Sıra" in header_txt or "ira" in header_txt
                has_derece = "Derece" in header_txt
                if not (has_sira and has_derece):
                    continue

                kosu_no += 1
                meta = kosu_meta.get(kosu_no, {})

                for tr in elem.find_all("tr"):
                    tds   = tr.find_all("td")
                    if len(tds) < 6: continue
                    cells = [td.get_text(" ", strip=True) for td in tds]

                    sira_txt = cells[0].strip()
                    if not sira_txt or not re.match(r"^\d+$", sira_txt): continue
                    sira = int(sira_txt)

                    at_id = at_url = ""
                    for a in tr.select("a[href*='/at/']"):
                        href = a.get("href","")
                        m2   = re.match(r".*/at/(\d+)/([^\s?#\"']+)", href)
                        if m2:
                            at_id  = m2.group(1)
                            at_url = f"https://yenibeygir.com/at/{at_id}/{m2.group(2)}"
                            break

                    at_adi = ""
                    if at_url:
                        slug   = at_url.rstrip("/").split("/")[-1]
                        at_adi = slug.replace("-"," ").upper()

                    at_cell = tds[1].get_text(" ", strip=True) if len(tds)>1 else ""
                    takiler = re.findall(r"\b(SKG|SK|DB|YP|KG|BP)\b", at_cell)
                    taki    = " ".join(dict.fromkeys(takiler))

                    derece  = cells[8]  if len(cells)>8  else ""
                    hiz_ind = cells[9]  if len(cells)>9  else ""
                    gny     = cells[10] if len(cells)>10 else ""
                    agf     = cells[11] if len(cells)>11 else ""
                    fark    = cells[12] if len(cells)>12 else ""

                    hiz_num = None
                    hm = re.search(r"\(?([+-]?\d+)\)?", str(hiz_ind))
                    if hm:
                        try: hiz_num = int(hm.group(1))
                        except: pass

                    msf_val = meta.get("msf","")
                    hiz_ms  = None
                    d_sec   = derece_to_sec(derece)
                    if d_sec and msf_val:
                        try: hiz_ms = round(int(msf_val) / d_sec, 3)
                        except: pass

                    tum_rows.append({
                        "kosu_no": kosu_no,
                        "sira":    sira,
                        "at":      at_adi,
                        "at_id":   at_id,
                        "at_url":  at_url,
                        "taki":    taki,
                        "yas":     cells[2].strip() if len(cells)>2 else "",
                        "kilo":    cells[3].strip() if len(cells)>3 else "",
                        "jokey":   cells[4].strip() if len(cells)>4 else "",
                        "klv":     cells[7].strip() if len(cells)>7 else "",
                        "derece":  derece,
                        "hiz_ind": hiz_num,
                        "gny":     gny,
                        "agf":     agf,
                        "fark":    fark,
                        "msf":     msf_val,
                        "pist":    meta.get("pist",""),
                        "hiz_ms":  hiz_ms,
                        "yildiz":  "",
                    })
        return tum_rows

    def _cek_sonuclar(self):
        if not BS4:
            messagebox.showerror("Hata","beautifulsoup4 gerekli."); return
        tarih = self.e_tarih.get().strip()
        sehir = self.sehir_var.get().strip()
        if not tarih or not sehir:
            messagebox.showwarning("Uyari","Tarih ve sehir secin."); return
        threading.Thread(target=self._sonuc_worker, args=(tarih,sehir), daemon=True).start()

    def _sonuc_worker(self, tarih, sehir):
        self.prog.start(10)
        self._st(f"Sonuclar cekiliyor: {tarih} {sehir}...")
        try:
            rows = self._scrape_sonuclar(tarih, sehir)
            if not rows:
                self.after(0, lambda: messagebox.showwarning("Sonuc Yok",
                    "Sonuc bulunamadi.\n• Kosu bitti mi?\n• Tarih/sehir dogru mu?"))
                return
            self._sonuc_rows = rows
            self.after(0, lambda: self._on_sonuclar(rows))
            self._st(f"OK {len(rows)} at sonucu")
        except Exception as e:
            self.after(0, lambda e2=str(e): messagebox.showerror("Hata", f"Sonuc:\n{e2}"))
            self._st(f"HATA: {e}")
        finally:
            self.prog.stop()

    def _on_sonuclar(self, rows):
        kosular = sorted(set(r["kosu_no"] for r in rows))
        vals    = ["Tumu"] + [f"{k}. Kosu" for k in kosular]
        self.sonuc_kosu_cb["values"] = vals
        self.sonuc_kosu_var.set("Tumu")
        self._yildizla()
        self._filtrele_sonuclar()
        self.sonuc_info.set(f"{len(rows)} at  |  {len(kosular)} kosu")

    def _yildizla(self):
        if not hasattr(self,"_sonuc_rows"): return
        try: esik = int(self.yildiz_esik_var.get())
        except: esik = 30

        from collections import defaultdict
        kosu_hizlar = defaultdict(list)
        for r in self._sonuc_rows:
            if r["hiz_ms"]: kosu_hizlar[r["kosu_no"]].append(r["hiz_ms"])

        kosu_stats = {}
        for k, vals in kosu_hizlar.items():
            ort = sum(vals)/len(vals)
            std = (sum((v-ort)**2 for v in vals)/max(len(vals),1))**0.5
            kosu_stats[k] = {"ort": ort, "std": max(std, 0.01)}

        for r in self._sonuc_rows:
            yildiz = ""
            hiz    = r.get("hiz_ind")
            hiz_ms = r.get("hiz_ms")
            sira   = r.get("sira", 99)
            kno    = r["kosu_no"]
            stats  = kosu_stats.get(kno, {})

            if isinstance(hiz, int):
                if hiz >= esik + 20:  yildiz += "YYYYY"
                elif hiz >= esik + 10: yildiz += "YYYY"
                elif hiz >= esik:      yildiz += "YYY"

            if hiz_ms and stats:
                ort = stats["ort"]; std = stats["std"]
                if hiz_ms >= ort + std and sira <= 3:
                    yildiz += "S"
                elif hiz_ms >= ort + std*0.5:
                    yildiz += "P"

            # Emoji donusum
            yildiz = (yildiz
                .replace("YYYYYS","★★★🌟")
                .replace("YYYYP","★★★✨")
                .replace("YYYYY","★★★")
                .replace("YYYYS","★★🌟")
                .replace("YYYYP","★★✨")
                .replace("YYYY","★★")
                .replace("YYYS","★🌟")
                .replace("YYYP","★✨")
                .replace("YYY","★")
                .replace("S","🌟").replace("P","✨"))

            r["yildiz"] = yildiz

        self._filtrele_sonuclar()
        n_star = sum(1 for r in self._sonuc_rows if r.get("yildiz"))
        self.sonuc_info.set(f"{len(self._sonuc_rows)} at  |  {n_star} yildizli  |  esik: hiz>={esik}")

    def _filtrele_sonuclar(self):
        if not hasattr(self,"_sonuc_rows"): return
        secim = self.sonuc_kosu_var.get()
        rows  = self._sonuc_rows
        if secim and secim not in ("Tumu","Tümü"):
            m = re.search(r"(\d+)", secim)
            if m: rows = [r for r in rows if r["kosu_no"] == int(m.group(1))]

        df = pd.DataFrame(rows)
        if df.empty: return
        show = ["yildiz","kosu_no","sira","at","taki","derece",
                "hiz_ms","hiz_ind","kilo","jokey","msf","pist","gny","agf","fark"]
        show = [c for c in show if c in df.columns]
        df   = df.sort_values(["kosu_no","sira"]).reset_index(drop=True)

        def tag_fn(row, idx):
            y = str(row.get("yildiz",""))
            s = row.get("sira",99)
            try: s = int(s)
            except: s = 99
            if "★★★" in y or "🌟" in y: return "g1"
            if "★★" in y:  return "g2"
            if "★" in y:   return "g3"
            if s == 1:  return "up"
            if s <= 3:  return "st"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_sonuc, df[show], tag_fn=tag_fn)
        self._draw_sonuc_chart()

    def _draw_sonuc_chart(self):
        cv = self.cv_sonuc; cv.delete("all")
        W  = cv.winfo_width() or 380; H = cv.winfo_height() or 420
        if not hasattr(self,"_sonuc_rows") or W < 80: return

        secim = self.sonuc_kosu_var.get()
        rows  = self._sonuc_rows
        if secim and secim not in ("Tumu","Tümü"):
            m = re.search(r"(\d+)", secim)
            if m: rows = [r for r in rows if r["kosu_no"] == int(m.group(1))]

        data = [(r["at"], r["hiz_ms"], r.get("yildiz",""), r["sira"])
                for r in rows if r.get("hiz_ms")]
        if not data: return
        data.sort(key=lambda x: x[1], reverse=True)
        data = data[:14]

        PL,PR,PT,PB = 52,14,40,68
        vals = [v for _,v,_,_ in data]
        mn = max(0, min(vals)-0.2); mx = max(vals)+0.2; rng = max(mx-mn,0.1)
        n  = len(data); bw = max(10, int((W-PL-PR)/n)-4); xs=(W-PL-PR)/n

        cv.create_text(W//2,20,text="Hiz m/s — En Hizlidan Yavasa",fill=TEXT,font=F_S)

        for frac in [0,0.25,0.5,0.75,1.0]:
            val = mn+frac*rng; y = PT+(1-frac)*(H-PT-PB)
            cv.create_line(PL,y,W-PR,y,fill=BORDER,dash=(2,5))
            cv.create_text(PL-5,y,text=f"{val:.2f}",fill=DIM,font=F_XS,anchor="e")

        for i,(at,hiz,yildiz,sira) in enumerate(data):
            frac = (hiz-mn)/rng; bh = max(4,int(frac*(H-PT-PB)))
            x0 = PL+i*xs+(xs-bw)/2; x1=x0+bw; y1=H-PB; y0=y1-bh
            col = GOLD if ("★★★" in yildiz or "🌟" in yildiz) else                   GREEN if "★★" in yildiz else TEAL if "★" in yildiz else BLUE
            cv.create_rectangle(x0,y0,x1,y1,fill=col,outline=BG)
            cv.create_text((x0+x1)/2,y0-5,text=f"{hiz:.2f}",fill=col,font=F_XS)
            sc = GOLD if sira==1 else SILVER if sira==2 else BRONZE if sira==3 else DIM
            cv.create_text((x0+x1)/2,y1+4,text=f"{sira}.",fill=sc,font=F_XS)
            if yildiz:
                cv.create_text((x0+x1)/2,y0-15,text=yildiz[:4],fill=GOLD,font=F_XS)
            cv.create_text((x0+x1)/2,H-PB+14,text=at[:9],
                           fill=TEXT,font=F_XS,angle=40,anchor="nw")

        cv.create_line(PL,PT,PL,H-PB,fill=DIM)
        cv.create_line(PL,H-PB,W-PR,H-PB,fill=DIM)


    # ── Tab: Karşılaştırma ───────────────────────────────

    def _build_karsi_tab(self, parent):
        tk.Label(parent,
                 text="Galop hızı + koşu stili + performans trendi birleşik karşılaştırma",
                 font=F_XS, bg=BG, fg=DIM).pack(anchor="w", padx=8, pady=(8,4))

        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        self.tree_karsi = self._make_tree(lp)

        rp = tk.Frame(mid, bg=BG, width=460)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Karşılaştırma Radar",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_karsi = tk.Canvas(rp, bg=PANEL,
                                   highlightthickness=1, highlightbackground=BORDER)
        self.cv_karsi.pack(fill="both", expand=True)
        self.cv_karsi.bind("<Configure>", lambda e: self._draw_karsi_chart())

    # ── Yardımcılar ──────────────────────────────────────

    def _make_tree(self, parent):
        f = tk.Frame(parent, bg=PANEL,
                     highlightthickness=1, highlightbackground=BORDER)
        f.pack(fill="both", expand=True, pady=(0,4))
        vsb = ttk.Scrollbar(f, orient="vertical")
        hsb = ttk.Scrollbar(f, orient="horizontal")
        tree = ttk.Treeview(f, show="headings",
                             yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)
        tree.tag_configure("g1",  background="#1F3A12", foreground=GOLD)
        tree.tag_configure("g2",  background="#112233", foreground=SILVER)
        tree.tag_configure("g3",  background="#2A1A08", foreground=BRONZE)
        tree.tag_configure("up",  background="#0F2A18", foreground=GREEN)
        tree.tag_configure("dn",  background="#2A0F0F", foreground=RED)
        tree.tag_configure("st",  background="#1A1A0A", foreground=YELLOW)
        tree.tag_configure("odd", background="#162030")
        tree.tag_configure("ev",  background=PANEL)
        return tree

    def _fill_tree(self, tree, df, tag_fn=None):
        tree.delete(*tree.get_children())
        if df is None or df.empty: return
        cols = list(df.columns)
        tree["columns"] = cols
        for c in cols:
            w = 130 if c in ("At","at","Jokey","KosuAdi") else 90
            tree.heading(c, text=c.replace("_"," "),
                         command=lambda _c=c, _t=tree: self._sort(_t,_c))
            tree.column(c, width=w, anchor="center", minwidth=55)
        for idx, row in df.iterrows():
            tag = "odd" if idx%2==0 else "ev"
            if tag_fn: tag = tag_fn(row, idx) or tag
            vals = []
            for c in cols:
                v = row.get(c, "")
                if isinstance(v, float):
                    v = f"{v:+.3f}" if abs(v) < 10 else f"{v:.1f}"
                vals.append(str(v) if v is not None else "")
            tree.insert("","end", values=vals, tags=(tag,))

    def _sort(self, tree, col):
        items = [(tree.set(c,col),c) for c in tree.get_children("")]
        try:    items.sort(key=lambda x: float(re.sub(r"[^\d.\-]","",x[0]) or "0"))
        except: items.sort(key=lambda x: x[0])
        for i,(_,c) in enumerate(items): tree.move(c,"",i)

    def _st(self, msg):
        self.st_var.set(msg); self.update_idletasks()

    def _onceki_gun(self):
        try:
            d = datetime.strptime(self.e_tarih.get(),"%d.%m.%Y") - timedelta(days=1)
            self.e_tarih.delete(0,"end"); self.e_tarih.insert(0,d.strftime("%d.%m.%Y"))
        except: pass

    def _sonraki_gun(self):
        try:
            d = datetime.strptime(self.e_tarih.get(),"%d.%m.%Y") + timedelta(days=1)
            self.e_tarih.delete(0,"end"); self.e_tarih.insert(0,d.strftime("%d.%m.%Y"))
        except: pass

    # ── Bülten çekimi ────────────────────────────────────

    def cek_bulten(self):
        if not self._ready:
            messagebox.showwarning("Bekle","Sistem hazırlanıyor."); return
        if not BS4:
            messagebox.showerror("Hata","beautifulsoup4 gerekli. pip install beautifulsoup4"); return
        tarih = self.e_tarih.get().strip()
        sehir = self.sehir_var.get().strip()
        if not tarih or not sehir:
            messagebox.showwarning("Uyarı","Tarih ve şehir seçin."); return
        threading.Thread(target=self._cek_bulten_worker,
                         args=(tarih,sehir), daemon=True).start()

    def _cek_bulten_worker(self, tarih, sehir):
        self.prog.start(10)
        self._st(f"Bülten çekiliyor: {tarih} {sehir}…")
        try:
            b = scrape_bulten(tarih, sehir)
            self.bulten = b
            self.after(0, lambda: self._on_bulten(b))
            self._st(f"✓ {len(b['kosular'])} koşu bulundu  —  {sehir.title()} {tarih}")
        except Exception as e:
            self.after(0, lambda e2=str(e):
                       messagebox.showerror("Hata", f"Bülten çekilemedi:\n{e2}"))
            self._st(f"HATA: {e}")
        finally: self.prog.stop()

    def _on_bulten(self, b):
        kosular = b.get("kosular", [])
        if not kosular:
            messagebox.showwarning("Sonuç Yok","Koşu bulunamadı."); return

        vals = []
        for k in kosular:
            n_at = len(k.get("atlar",[]))
            label = (f"{k['no']}. Koşu  {k['saat']}  |  "
                     f"{k['cins']}  {k['mesafe']}m {k['pist']}  |  "
                     f"{n_at} at")
            vals.append(label)
        self.kosu_cb["values"] = vals
        if vals:
            self.kosu_cb.current(0)
            self._sec_kosu()

    def _sec_kosu(self):
        """Seçili koşunun atlarını sol panele doldur."""
        idx = self.kosu_cb.current()
        if idx < 0 or not self.bulten: return
        kosular = self.bulten.get("kosular",[])
        if idx >= len(kosular): return
        self.sel_kosu = kosular[idx]
        self._fill_at_listesi(self.sel_kosu)

    def _fill_at_listesi(self, kosu):
        self.at_tree.delete(*self.at_tree.get_children())
        atlar = kosu.get("atlar",[])

        # Koşu özet
        self.kosu_info.config(
            text=f"{'  '.join(filter(None,[kosu.get('cins',''),kosu.get('mesafe','')+'m',kosu.get('pist',''),kosu.get('para','₺')]))}"
        )

        for i, at in enumerate(atlar):
            son10_str = at.get("son10_str","—")
            # Son 10'dan form skoru: küçük sayı iyi
            son10 = at.get("son10",[])
            form_skor = sum(1 for s in son10[-3:] if s<=3) if son10 else 0

            if form_skor >= 2:   tag = "good"
            elif form_skor == 1: tag = "mid"
            else:                tag = "odd" if i%2==0 else "ev"

            self.at_tree.insert("","end",
                values=(at.get("no",""), at.get("at",""),
                        at.get("agf",""), son10_str,
                        at.get("hnd",""), at.get("taki","")),
                tags=(tag,))

    def _filter_atlar(self):
        """Filtre kutusuna göre at listesini filtrele."""
        q = self.at_filter.get().lower().strip()
        if not self.sel_kosu: return
        self.at_tree.delete(*self.at_tree.get_children())
        for i, at in enumerate(self.sel_kosu.get("atlar",[])):
            if q and q not in at.get("at","").lower(): continue
            tag = "odd" if i%2==0 else "ev"
            self.at_tree.insert("","end",
                values=(at.get("no",""), at.get("at",""),
                        at.get("agf",""), at.get("son10_str","—"),
                        at.get("hnd",""), at.get("taki","")),
                tags=(tag,))

    # ── Analiz çalıştır ──────────────────────────────────

    def analiz_kosu(self):
        if not self._ready:
            messagebox.showwarning("Bekle","Sistem hazırlanıyor."); return
        if not self.sel_kosu:
            messagebox.showwarning("Uyarı","Önce bülten çekip koşu seçin."); return
        threading.Thread(target=self._analiz_worker, daemon=True).start()

    def _analiz_worker(self):
        self.prog.start(10)
        kosu   = self.sel_kosu
        tarih  = self.bulten["tarih"]
        sehir  = self.bulten["sehir"]
        kosu_no= kosu["no"]

        # 1. Galopları çek
        self._st(f"Galoplar çekiliyor: {kosu_no}. koşu…")
        try:
            g_rows = scrape_galoplar(tarih, sehir, kosu_no)
            self.galoplar = g_rows
            self.galop_an = analiz_galop(g_rows)
            self._st(f"✓ {len(g_rows)} galop kaydı")
        except Exception as e:
            self._st(f"Galop hatası: {e}")
            self.galoplar = []
            self.galop_an = {}

        # 2. Her at için profil çek
        atlar = kosu.get("atlar",[])
        total = sum(1 for a in atlar if a.get("at_url"))
        done  = 0
        self.profiller.clear(); self.stiller.clear(); self.performlar.clear()

        # Koşu mesafe ve pist bilgisi
        try:
            k_mesafe = int(kosu.get("mesafe", "0"))
        except (ValueError, TypeError):
            k_mesafe = 0
        k_pist = kosu.get("pist", "")

        for at in atlar:
            url = at.get("at_url","")
            if not url: continue
            at_adi = at.get("at","")
            done += 1
            self._st(f"Profil çekiliyor [{done}/{total}]: {at_adi}…")
            try:
                profil = scrape_profil(url)
                self.profiller[at_adi] = profil
                trakus_at = self.tempo_an.get(at_adi, {})
                self.stiller[at_adi]   = analiz_stil(profil, k_mesafe, k_pist,
                                                      trakus_data=trakus_at)
                self.performlar[at_adi]= analiz_perform(profil)
            except Exception as e:
                self._st(f"Profil hatası ({at_adi}): {e}")

        self.prog.stop()
        self.after(0, self._guncelle_tum_tablolar)
        self._st(f"✓ Analiz tamamlandı  —  {len(self.stiller)} at profil yüklendi")

    def _guncelle_tum_tablolar(self):
        self._update_genel()
        self._update_galop_tab()
        self._update_stil_tab()
        self._update_trend_tab()
        self._update_karsi_tab()
        self._update_son2hiz()
        self._update_takip()
        self._update_senaryo()
        self._update_trakus_tab()
        self._update_genel_yaris()

    # ── Genel Analiz ─────────────────────────────────────

    def _update_genel(self):
        if not self.sel_kosu: return
        atlar = self.sel_kosu.get("atlar",[])
        rows  = []
        for at in atlar:
            adi = at.get("at","")
            g   = self.galop_an.get(adi,{})
            s   = self.stiller.get(adi,{})
            p   = self.performlar.get(adi,{})

            # Birleşik skor (gelişmiş)
            skor = 0.0
            if g.get("en_iyi_400"):
                skor += max(0, min(30, (27-g["en_iyi_400"])*4))
            if g.get("gun_fark") is not None:
                skor += max(0, 8-g["gun_fark"]*0.4)
            if g.get("galop_trend_skor"):
                skor += min(7, g["galop_trend_skor"] * 5)
            if s.get("ilk3_pct"):
                skor += s["ilk3_pct"]*0.25
            if s.get("stil_skor"):
                skor += s["stil_skor"] * 0.1
            if s.get("mesafe_uyum_skor"):
                skor += s["mesafe_uyum_skor"] * 3
            if p.get("trend_skor"):
                skor += p["trend_skor"]*25
            if p.get("momentum") == "🚀 İVMELENİYOR":
                skor += 5
            skor = round(skor, 1)

            rows.append({
                "No":          at.get("no",""),
                "At":          adi,
                "AGF":         at.get("agf",""),
                "Hnd":         at.get("hnd",""),
                "Son5_Form":   s.get("son5","—"),
                "Kosu_Stili":  s.get("stil","—"),
                "Stil_Skor":   s.get("stil_skor",""),
                "Ilk3_%":      s.get("ilk3_pct",""),
                "En_Iyi_400":  g.get("en_iyi_400",""),
                "Galop_Trend": g.get("galop_trend","—"),
                "Son_Galop":   g.get("gun_fark",""),
                "Trend":       p.get("trend","—"),
                "Momentum":    p.get("momentum","—"),
                "Msf_Uyum":    s.get("mesafe_uyumu","—"),
                "Tutarlılık":  s.get("tutarlilik","—"),
                "Taki":        at.get("taki",""),
                "Skor":        skor,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Skor",
                key=lambda x: pd.to_numeric(x,errors="coerce").fillna(0),
                ascending=False).reset_index(drop=True)

        def tag_fn(row, idx):
            if idx == 0: return "g1"
            if idx == 1: return "g2"
            if idx == 2: return "g3"
            t = str(row.get("Trend",""))
            if "YÜKSELİYOR" in t: return "up"
            if "DÜŞÜYOR"    in t: return "dn"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_genel, df, tag_fn=tag_fn)

        # Podium
        self._draw_podium(df.head(3).to_dict("records") if not df.empty else [])

        # Koşu bilgi kartı
        kosu = self.sel_kosu
        if kosu:
            msf = kosu.get("mesafe", "—")
            pist = kosu.get("pist", "—")
            ref = mesafe_tempo_bilgisi(int(msf), pist) if msf and msf.isdigit() else None
            info_txt = (f"📋 {kosu.get('no','')}. Koşu  |  "
                       f"Saat: {kosu.get('saat','—')}  |  "
                       f"Mesafe: {msf}m  |  Pist: {pist}  |  "
                       f"Cins: {kosu.get('cins','—')}  |  "
                       f"{len(kosu.get('atlar',[]))} at")
            if ref:
                ref_d = ref["ref_derece"]
                info_txt += (f"\n📏 Ref Derece: İyi={derece_formatla(ref_d[0])} "
                            f"Orta={derece_formatla(ref_d[1])} "
                            f"Zayıf={derece_formatla(ref_d[2])}  |  "
                            f"{ref['tempo_tipi']}")
            self.genel_kosu_lbl.config(text=info_txt)

        # Özet rapor
        self._write_genel_ozet(df)

    def _write_genel_ozet(self, df):
        """Genel analiz hızlı özet rapor."""
        lines = []
        if df is None or df.empty:
            lines.append("Analiz bekleniyor…")
        else:
            top3 = df.head(3).to_dict("records")
            lines.append(f"🏆 İLK 3 FAVORİ: " +
                         " | ".join(f"{r.get('At','')}: {r.get('Skor','')}" for r in top3))
            # Formda olanlar
            formda = df[df["Trend"].str.contains("YÜKSELİYOR", na=False)]
            if not formda.empty:
                lines.append("📈 FORMU YÜKSELEN: " +
                             ", ".join(formda["At"].head(4).tolist()))
            # Hazırlıklı olanlar
            if "Galop_Trend" in df.columns:
                hizli = df[df["Galop_Trend"].str.contains("HIZLANIYOR", na=False)]
                if not hizli.empty:
                    lines.append("🔥 GALOP HIZLANIYOR: " +
                                 ", ".join(hizli["At"].head(4).tolist()))
            # Mesafe uyumlu
            if "Msf_Uyum" in df.columns:
                uyumlu = df[df["Msf_Uyum"].str.contains("ÇOK İYİ|İYİ", na=False)]
                if not uyumlu.empty:
                    lines.append("📏 MESAFE UYUMLU: " +
                                 ", ".join(uyumlu["At"].head(4).tolist()))

        self.txt_genel.config(state="normal")
        self.txt_genel.delete("1.0", "end")
        self.txt_genel.insert("end", "\n".join(lines))
        self.txt_genel.config(state="disabled")

    def _draw_podium(self, top3):
        for w in self.pod.winfo_children(): w.destroy()
        tk.Label(self.pod, text="🏆  En Güçlü Adaylar",
                 font=F_M, bg=BG, fg=TEXT).pack(side="left", padx=(0,16))
        medals = ["🥇","🥈","🥉"]; colors = [GOLD,SILVER,BRONZE]
        for i, row in enumerate(top3):
            c = tk.Frame(self.pod, bg=CARD,
                         highlightthickness=2, highlightbackground=colors[i],
                         padx=14, pady=8)
            c.pack(side="left", padx=(0,10))
            tk.Label(c, text=f"{medals[i]} {row.get('At','')}",
                     font=F_M, bg=CARD, fg=TEXT).pack()
            tk.Label(c, text=f"Skor: {row.get('Skor','—')}",
                     font=("Segoe UI",12,"bold"), bg=CARD, fg=colors[i]).pack()
            details = f"{row.get('Kosu_Stili','—')}  |  Form: {row.get('Son5_Form','—')}"
            tk.Label(c, text=details, font=F_XS, bg=CARD, fg=DIM).pack(pady=(2,0))

    # ── Galop Tab ─────────────────────────────────────────

    def _update_galop_tab(self):
        if not self.galop_an: return
        horses = ["Tümü"] + sorted(self.galop_an.keys())
        self.g_horse_cb["values"] = horses
        self.g_horse_var.set("Tümü")   # hep Tümü ile aç
        self._refresh_galop_detail()
        # Galop sekmesine geç (sekme index 1)
        self.nb.select(1)

    def _refresh_galop_detail(self):
        horse = self.g_horse_var.get()
        n_str = self.g_n_var.get()

        # Tümü = hepsi, seçili = sadece o at
        rows = [r for r in self.galoplar
                if horse == "Tümü" or r.get("at","") == horse]
        df = pd.DataFrame(rows) if rows else pd.DataFrame()

        if not df.empty:
            df["_date"] = df["g_tarih"].apply(parse_date_key)
            if "400" in df.columns:
                df["_400s"] = df["400"].apply(galop_to_sec)
            else:
                df["_400s"] = None
            df["_gun"]  = df["g_tarih"].apply(gun_farki)

            # Her at için son N galop al (tarihe göre)
            def son_n(grp):
                g2 = grp.sort_values("_date", ascending=False)
                if n_str != "Tümü":
                    try: g2 = g2.head(int(n_str))
                    except: pass
                return g2

            df = df.groupby("at", group_keys=False).apply(son_n).reset_index(drop=True)

            # Ağırlıklı skor: hız (büyük = iyi) + tazelik bonusu
            MAX_SEC = 35.0
            df["_hiz_skor"] = df["_400s"].apply(
                lambda s: (MAX_SEC - s) * 3 if pd.notna(s) and s and s > 0 else 0
            )
            df["_taze"] = df["_gun"].apply(
                lambda g: 8 if g is not None and g <= 3
                     else 5 if g is not None and g <= 7
                     else 2 if g is not None and g <= 14
                     else 0
            )
            df["_skor"] = df["_hiz_skor"] + df["_taze"]

            # ── Düz liste: tüm atlar, en iyiden en kötüye ──────
            df = df.sort_values("_skor", ascending=False,
                                na_position="last").reset_index(drop=True)

            # Görsel sütunlar
            df["Tazelik"] = df["_gun"].apply(
                lambda g: "🟢 Bugün" if g == 0
                     else f"🟢 {g}g"  if g is not None and g <= 3
                     else f"🟡 {g}g"  if g is not None and g <= 7
                     else f"🟠 {g}g"  if g is not None and g <= 14
                     else f"⚫ {g}g"  if g is not None
                     else "—"
            )
            df["Skor"] = df["_skor"].round(1)

            # Galop trend, yoğunluk ve hazırlık durumu
            df["Galop_Trend"] = df["at"].apply(
                lambda a: self.galop_an.get(a, {}).get("galop_trend", "—"))
            df["Yoğunluk"] = df["at"].apply(
                lambda a: self.galop_an.get(a, {}).get("galop_yogunluk", "—"))
            df["Hazırlık"] = df["at"].apply(
                lambda a: self._galop_hazirlik(a))

            df = df.drop(columns=["_date","_400s","_gun","_hiz_skor","_taze","_skor"],
                         errors="ignore")

        show = ["Skor","no","at","Hazırlık","Tazelik","Galop_Trend","Yoğunluk",
                "g_tarih","400","600","800","1000","1200","1400",
                "g_sehir","kg","jokey","pist"]
        show = [c for c in show if not df.empty and c in df.columns]

        def tag_fn(row, idx):
            if idx == 0: return "g1"
            if idx == 1: return "g2"
            if idx == 2: return "g3"
            haz = str(row.get("Hazırlık",""))
            if "YARIŞA HAZIR" in haz: return "up"
            if "FORMA" in haz: return "st"
            if "SOĞUK" in haz: return "dn"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_galop,
                        df[show] if show and not df.empty else df,
                        tag_fn=tag_fn)
        self.after(80, self._draw_galop_bar)
        self._write_galop_rapor()

    def _write_galop_rapor(self):
        """Detaylı galop raporu — at bazında hazırlık durumu + mesafe analizi."""
        lines = []
        if not self.galop_an:
            lines.append("Henüz galop verisi yok. Bülten çekip koşu analizi yapın.")
        else:
            lines.append(f"📋 GALOP RAPORU — {len(self.galop_an)} at analiz edildi")
            lines.append("═" * 70)

            # Hazırlık sıralaması
            atlar_hazir = []
            for at, g in self.galop_an.items():
                hazirlik = self._galop_hazirlik(at)
                atlar_hazir.append((at, g, hazirlik))

            # Yarışa hazır olanlar
            hazirlar = [(a, g, h) for a, g, h in atlar_hazir if "YARIŞA HAZIR" in h or "FORMA" in h]
            if hazirlar:
                lines.append("")
                lines.append("🔥 YARIŞA HAZIR / FORMA GİREN ATLAR:")
                for at, g, haz in hazirlar:
                    gun = g.get("gun_fark", "?")
                    en_iyi = g.get("en_iyi_400")
                    ort = g.get("ort_400")
                    trend = g.get("galop_trend", "—")
                    toplam = g.get("galop_sayisi", 0)
                    en_iyi_t = f"{en_iyi:.2f}s" if en_iyi else "—"
                    ort_t = f"{ort:.2f}s" if ort else "—"
                    lines.append(
                        f"   🐎 {at}: {haz}")
                    lines.append(
                        f"      Son galop: {gun} gün önce | "
                        f"Toplam: {toplam} galop | "
                        f"En iyi 400m: {en_iyi_t} | Ort: {ort_t} | {trend}")

                    # Mesafe bazlı dereceler
                    ma = g.get("mesafe_analiz", {})
                    if ma:
                        msf_parts = []
                        for msf in ["400","600","800","1000","1200","1400"]:
                            if msf in ma:
                                msf_parts.append(
                                    f"{msf}m:{ma[msf]['en_iyi']:.1f}s")
                        if msf_parts:
                            lines.append(f"      Mesafe: {' | '.join(msf_parts)}")

            # Soğuk atlar
            soguklar = [(a, g, h) for a, g, h in atlar_hazir if "SOĞUK" in h or "SOĞUYOR" in h]
            if soguklar:
                lines.append("")
                lines.append("⚫ SOĞUK / UZUN ARA:")
                for at, g, haz in soguklar:
                    gun = g.get("gun_fark", "?")
                    lines.append(f"   • {at}: Son galop {gun} gün önce — {haz}")

            # En iyi 400m sıralaması
            lines.append("")
            lines.append("─" * 70)
            lines.append("📊 EN İYİ 400m SIRALAMASI:")
            sirali = sorted(self.galop_an.items(),
                           key=lambda x: x[1].get("en_iyi_400") or 999)
            for i, (at, g) in enumerate(sirali[:10], 1):
                en_iyi = g.get("en_iyi_400")
                if en_iyi:
                    bar_len = max(0, int((30 - en_iyi) * 5))
                    bar = "█" * bar_len
                    lines.append(f"   {i:2d}. {at:<20s} {en_iyi:.2f}s  {bar}")

        self.txt_galop.config(state="normal")
        self.txt_galop.delete("1.0", "end")
        self.txt_galop.insert("end", "\n".join(lines))
        self.txt_galop.config(state="disabled")

    def _galop_hazirlik(self, at_adi):
        """Galop verilerinden hazırlık/form durumu belirle."""
        g = self.galop_an.get(at_adi, {})
        if not g:
            return "❓ VERİ YOK"

        gun = g.get("gun_fark")
        yogunluk = g.get("galop_yogunluk", "")
        trend = g.get("galop_trend", "")
        toplam = g.get("galop_sayisi", 0)
        en_iyi = g.get("en_iyi_400")
        ort = g.get("ort_400")

        # Sıkı hazırlık + hızlanıyor + taze = YARIŞA HAZIR
        if (gun is not None and gun <= 5 and
            toplam >= 3 and
            "YOĞUN" in yogunluk or "AKTİF" in yogunluk):
            if "HIZLANIYOR" in trend:
                return "🔥 YARIŞA HAZIR (sıkı+hızlı)"
            return "🟢 YARIŞA HAZIR (aktif hazırlık)"

        if gun is not None and gun <= 7 and toplam >= 2:
            if "HIZLANIYOR" in trend:
                return "🟢 FORMA GİRİYOR (hızlanıyor)"
            if en_iyi and ort and en_iyi < ort - 0.5:
                return "🟢 FORMA GİRİYOR (patlama var)"
            return "🟡 HAZIRLIK VAR"

        if gun is not None and gun <= 14:
            if toplam >= 2:
                return "🟡 NORMAL HAZIRLIK"
            return "🟠 AZ GALOP"

        if gun is not None and gun <= 21:
            return "🟠 SOĞUYOR"

        if gun is not None and gun > 21:
            return "⚫ SOĞUK (uzun ara)"

        return "❓ BELİRSİZ"

    def _draw_galop_bar(self):
        cv = self.cv_galop; cv.delete("all")
        W  = cv.winfo_width() or 380; H = cv.winfo_height() or 400
        if not self.galop_an or W < 80: return

        items = []
        for at, d in self.galop_an.items():
            v = d.get("en_iyi_400")
            if v: items.append((at, v))
        if not items: return
        items.sort(key=lambda x: x[1])

        PL,PR,PT,PB = 50,12,36,60
        mn = items[0][1]; mx = items[-1][1]; rng = max(mx-mn,0.5)
        n  = len(items); bw = max(12, int((W-PL-PR)/n)-4); xs=(W-PL-PR)/n

        cv.create_text(W//2,18,
                       text="En İyi 400m  (küçük = hızlı)",
                       fill=TEXT, font=F_S)
        for frac in [0,0.25,0.5,0.75,1.0]:
            val = mn+frac*rng; y = PT+(1-frac)*(H-PT-PB)
            cv.create_line(PL,y,W-PR,y,fill=BORDER,dash=(2,5))
            cv.create_text(PL-5,y,text=f"{val:.1f}",fill=DIM,font=F_XS,anchor="e")

        for i,(at,val) in enumerate(items):
            frac = (val-mn)/rng if rng>0 else 0.5
            bh   = max(4, int(frac*(H-PT-PB)))
            x0   = PL+i*xs+(xs-bw)/2; x1=x0+bw
            y1   = H-PB; y0=y1-bh
            gun  = self.galop_an.get(at,{}).get("gun_fark",99) or 99
            col  = GREEN if gun<=7 else (YELLOW if gun<=14 else BLUE)
            cv.create_rectangle(x0,y0,x1,y1,fill=col,outline=BG,width=1)
            cv.create_text((x0+x1)/2,y0-5,text=f"{val:.1f}",fill=col,font=F_XS)
            cv.create_text((x0+x1)/2,H-PB+14,
                           text=at[:10],fill=DIM,font=F_XS,angle=42,anchor="nw")

        cv.create_line(PL,PT,PL,H-PB,fill=DIM)
        cv.create_line(PL,H-PB,W-PR,H-PB,fill=DIM)
        # Legend
        for col,lbl,x in [(GREEN,"≤7 gün",PL),(YELLOW,"≤14 gün",PL+70),(BLUE,">14 gün",PL+145)]:
            cv.create_rectangle(x,H-PB+48,x+10,H-PB+58,fill=col,outline="")
            cv.create_text(x+13,H-PB+53,text=lbl,fill=col,font=F_XS,anchor="w")

    # ── Stil Tab ─────────────────────────────────────────

    def _update_stil_tab(self):
        if not self.stiller: return
        self.stil_status.set(f"✓ {len(self.stiller)} at — stil + form + tutarlılık analizi")
        rows = []
        for at, s in self.stiller.items():
            pp = s.get("pozisyon_profili", {})
            poz_txt = ""
            if pp:
                poz_txt = f"{pp.get('erken_poz','—')}→{pp.get('son_poz','—')}"
            rows.append({
                "At":          at,
                "Stil":        s.get("stil",""),
                "Stil_Skor":   s.get("stil_skor",""),
                "Pozisyon":    poz_txt,
                "Form":        s.get("form_notu",""),
                "Tutarlılık":  s.get("tutarlilik",""),
                "Msf_Uyum":    s.get("mesafe_uyumu","")[:25] if s.get("mesafe_uyumu") else "",
                "Pist_Uyum":   s.get("pist_uyumu","")[:25] if s.get("pist_uyumu") else "",
                "Ort_Sıra":    s.get("ort_sira",""),
                "İlk3_%":      s.get("ilk3_pct",""),
                "Kazanma_%":   s.get("kazanma_oran",""),
                "Son5":        s.get("son5",""),
                "Mesafe_Pref": s.get("mesafe_pref","")[:25] if s.get("mesafe_pref") else "",
                "Ort_Hız":     s.get("ort_hiz",""),
                "Takı":        s.get("taki","")[:30] if s.get("taki") else "",
                "Koşu_Say":    s.get("toplam_kosu",""),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("İlk3_%",
                key=lambda x: pd.to_numeric(x,errors="coerce").fillna(0),
                ascending=False).reset_index(drop=True)

        def tag_fn(row, idx):
            s = str(row.get("Stil",""))
            f = str(row.get("Form",""))
            if "ZİRVEDE" in f or "FORMDA" in f: return "up"
            if "DÜŞÜŞTE" in f: return "dn"
            if "ÖNDE GİDER" in s or "Lider" in s: return "g1"
            if "ÖNDEN TAKİP" in s: return "g1"
            if "ORTADAN" in s: return "g2"
            if "YÜKSELİCİ" in s: return "st"
            if "GERİDEN" in s or "KAPANIŞÇI" in s: return "g3"
            if "ERKEN YORULAN" in s: return "dn"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_stil, df, tag_fn=tag_fn)

        # Kartlar — stil dağılımı + form özeti
        for w in self.stil_cards.winfo_children(): w.destroy()
        onderr  = sum(1 for s in self.stiller.values()
                      if "ÖNDE GİDER" in s.get("stil","") or "ÖNDEN TAKİP" in s.get("stil",""))
        ortadan = sum(1 for s in self.stiller.values()
                      if "ORTADAN" in s.get("stil","") or "YÜKSELİCİ" in s.get("stil","")
                      or "BELİRSİZ" in s.get("stil",""))
        geriden = sum(1 for s in self.stiller.values()
                      if "GERİDEN" in s.get("stil","") or "KAPANIŞÇI" in s.get("stil","")
                      or "ATAĞI" in s.get("stil",""))
        erken_yor = sum(1 for s in self.stiller.values()
                        if "ERKEN YORULAN" in s.get("stil",""))
        formda  = sum(1 for s in self.stiller.values()
                      if s.get("form_notu","") in ("🔥 ZİRVEDE","🟢 FORMDA","📈 YÜKSELİYOR"))
        tutarli = sum(1 for s in self.stiller.values()
                      if "TUTARLI" in str(s.get("tutarlilik","")) and "TUTARSIZ" not in str(s.get("tutarlilik","")))
        for lbl,val,col in [
            ("🟢 Önde Gider",  onderr,    GREEN),
            ("🟡 Ortadan",     ortadan,   YELLOW),
            ("🔵 Geriden/Kapanış", geriden, BLUE),
            ("🔴 Erken Yorulan",erken_yor, RED),
            ("🔥 Formda",      formda,    ORANGE),
            ("📊 Tutarlı",     tutarli,   TEAL),
            ("Toplam",         len(self.stiller), DIM),
        ]:
            c = tk.Frame(self.stil_cards, bg=CARD,
                         highlightthickness=2, highlightbackground=col,
                         padx=12, pady=6)
            c.pack(side="left", padx=(0,8))
            tk.Label(c,text=str(val),font=("Segoe UI",18,"bold"),bg=CARD,fg=col).pack()
            tk.Label(c,text=lbl,font=F_XS,bg=CARD,fg=DIM).pack()

        horses = ["Tümü"]+sorted(self.stiller.keys())
        self.stil_horse_cb["values"] = horses
        if len(horses)>1:
            self.stil_horse_var.set(horses[1])
            self._refresh_stil_detail()
        self._write_stil_rapor()

    def _refresh_stil_detail(self):
        horse = self.stil_horse_var.get()
        if not horse or horse=="Tümü" or horse not in self.profiller:
            self.stil_detay_lbl.config(text="")
            return
        races = self.profiller[horse].get("races",[])
        if not races: return

        # Detay kartı güncelle
        s = self.stiller.get(horse, {})
        detay_parts = [s.get("stil",""), " — ", s.get("stil_detay","")]

        # Pozisyon profili (Trakus verisi varsa)
        pp = s.get("pozisyon_profili", {})
        if pp:
            detay_parts.append(
                f"\nTrakus Pozisyon: Erken={pp.get('erken_poz','—')} → "
                f"Son={pp.get('son_poz','—')}  "
                f"Değişim: {pp.get('poz_degisim','—')}")

        detay_parts.append(f"\nForm: {s.get('form_notu','—')}  |  "
                           f"Tutarlılık: {s.get('tutarlilik','—')}  |  "
                           f"Kazanma: %{s.get('kazanma_oran',0)}  |  "
                           f"Stil Skor: {s.get('stil_skor','—')}")
        detay_parts.append(f"\nMesafe Uyumu: {s.get('mesafe_uyumu','—')}  |  "
                           f"Pist Uyumu: {s.get('pist_uyumu','—')}")
        detay_parts.append(f"\nMesafe Tercihi: {s.get('mesafe_pref','—')}  |  "
                           f"Pist: {s.get('pist_pref','—')}")
        pk = s.get("pist_kazanma",{})
        if pk:
            pk_str = "  ".join(f"{p}:{v}" for p,v in pk.items())
            detay_parts.append(f"\nPist Kazanma: {pk_str}")

        # Jokey istatistik
        ji = s.get("jokey_istatistik", {})
        if ji:
            j_parts = []
            for jokey, istat in list(ji.items())[:3]:
                j_parts.append(f"{jokey}({istat['kosu']} koşu, "
                              f"ort:{istat['ort_sira']}, "
                              f"kaz:{istat['kazanma']})")
            detay_parts.append(f"\nJokey: {' | '.join(j_parts)}")

        self.stil_detay_lbl.config(text="".join(detay_parts))

        df = pd.DataFrame(races)
        show = ["tarih","sehir","kcins","msf","pist","sira","derece","hiz","jokey","kilo","taki"]
        show = [c for c in show if c in df.columns]

        def tag_fn(row, idx):
            try:
                s = int(re.sub(r"[^\d]","",str(row.get("sira","") or "")))
                if s==1: return "g1"
                if s==2: return "g2"
                if s==3: return "g3"
            except: pass
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_stil_detail,
                        df[show] if show else df, tag_fn=tag_fn)

    def _write_stil_rapor(self):
        """Detaylı koşu stili raporu — stil dağılımı, yarış senaryosu, öneriler."""
        lines = []
        if not self.stiller:
            lines.append("Henüz stil analizi yapılmadı.")
        else:
            lines.append(f"📋 KOŞU STİLİ RAPORU — {len(self.stiller)} at analiz edildi")
            lines.append("═" * 70)

            # Stil gruplarına ayır
            gruplar = {
                "ÖNDE GİDER": [], "ÖNDEN TAKİP": [],
                "GERİDEN ATAĞI": [], "KAPANIŞÇI": [],
                "ORTADAN": [], "ERKEN YORULAN": [],
                "DİĞER": []
            }
            for at, s in self.stiller.items():
                stil_txt = s.get("stil", "")
                placed = False
                for gk in gruplar:
                    if gk in stil_txt:
                        gruplar[gk].append((at, s))
                        placed = True
                        break
                if not placed:
                    gruplar["DİĞER"].append((at, s))

            # Yarış senaryosu
            lines.append("")
            lines.append("🏁 YARIŞ SENARYOSU:")
            lines.append("─" * 50)
            onde = gruplar["ÖNDE GİDER"] + gruplar["ÖNDEN TAKİP"]
            if onde:
                lines.append(f"   ⚡ ÖNÜ ÇEKECEK: " +
                             ", ".join(f"{a}(skor:{s.get('stil_skor',0)})" for a, s in onde))
                if len(onde) >= 3:
                    lines.append("      ⚠ Çok kalabalık ön grup → tempo yüksek olabilir → kapanışçılara avantaj!")
                elif len(onde) <= 1:
                    lines.append("      ⚠ Tek kaçak at → kendi temposunu dikte edebilir!")
            else:
                lines.append("   ⚠ Belirgin kaçak at yok — ortadan gidişli koşu olabilir")

            geri = gruplar["GERİDEN ATAĞI"] + gruplar["KAPANIŞÇI"]
            if geri:
                lines.append(f"   🔵 KAPANICI: " +
                             ", ".join(f"{a}(skor:{s.get('stil_skor',0)})" for a, s in geri))
                if len(onde) >= 3:
                    lines.append("      ✅ Tempolu yarışta kapanışçılar avantajlı!")

            orta = gruplar["ORTADAN"]
            if orta:
                lines.append(f"   🟡 ORTADAN: " +
                             ", ".join(a for a, _ in orta))

            yorulan = gruplar["ERKEN YORULAN"]
            if yorulan:
                lines.append(f"   🔴 RİSKLİ (erken yorulma): " +
                             ", ".join(a for a, _ in yorulan))

            # Form + tutarlılık sıralaması
            lines.append("")
            lines.append("─" * 50)
            lines.append("📊 FORM + TUTARLILIK SIRASI:")
            formlu = sorted(self.stiller.items(),
                            key=lambda x: x[1].get("stil_skor", 0), reverse=True)
            for i, (at, s) in enumerate(formlu[:8], 1):
                form = s.get("form_notu", "—")
                tutar = s.get("tutarlilik", "—")
                skor = s.get("stil_skor", 0)
                son5 = s.get("son5", "—")
                msf_u = s.get("mesafe_uyumu", "—")
                if isinstance(msf_u, str) and len(msf_u) > 30:
                    msf_u = msf_u[:30]
                lines.append(
                    f"   {i:2d}. {at:<18s} Skor:{skor:5.1f}  "
                    f"Form:{form}  Tutarlılık:{tutar}")
                lines.append(
                    f"       Son5: {son5}  |  Mesafe: {msf_u}")

            # Trakus pozisyon verisi olan atlar
            trakus_atlar = [(at, s) for at, s in self.stiller.items()
                            if s.get("pozisyon_profili")]
            if trakus_atlar:
                lines.append("")
                lines.append("─" * 50)
                lines.append("📡 TRAKUS POZİSYON VERİSİ:")
                for at, s in trakus_atlar:
                    pp = s["pozisyon_profili"]
                    erken = pp.get("erken_poz", "—")
                    son = pp.get("son_poz", "—")
                    deg = pp.get("poz_degisim", 0)
                    deg_str = f"+{deg}" if deg > 0 else str(deg)
                    lines.append(
                        f"   🐎 {at}: Erken={erken} → Son={son} "
                        f"(değişim: {deg_str})  {s.get('stil','')}")

            # Jokey analizi
            lines.append("")
            lines.append("─" * 50)
            lines.append("🏇 JOKEY ETKİSİ:")
            for at, s in sorted(self.stiller.items(),
                                key=lambda x: x[1].get("stil_skor", 0), reverse=True)[:6]:
                ji = s.get("jokey_istatistik", {})
                if ji:
                    best_j = max(ji.items(),
                                 key=lambda x: x[1].get("kazanma", 0) + x[1].get("ilk3", 0),
                                 default=(None, {}))
                    if best_j[0]:
                        istat = best_j[1]
                        lines.append(
                            f"   {at}: En iyi jokey → {best_j[0]} "
                            f"({istat.get('kosu',0)} koşu, "
                            f"kaz:{istat.get('kazanma',0)}, "
                            f"ilk3:{istat.get('ilk3',0)})")

        self.txt_stil.config(state="normal")
        self.txt_stil.delete("1.0", "end")
        self.txt_stil.insert("end", "\n".join(lines))
        self.txt_stil.config(state="disabled")

    # ── Trend Tab ─────────────────────────────────────────

    def _update_trend_tab(self):
        if not self.performlar: return
        rows = []
        for at, p in self.performlar.items():
            rows.append({
                "At":          at,
                "Trend":       p.get("trend",""),
                "Momentum":    p.get("momentum","—"),
                "Trend_Skor":  p.get("trend_skor",""),
                "En_Iyi_Hiz":  p.get("en_iyi_hiz",""),
                "Ort_Hiz_ms":  p.get("ort_hiz_ms",""),
                "Kazanma_Hız": p.get("kazanma_hiz","—"),
                "Toplam_Yarış":p.get("toplam_yaris",""),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Trend_Skor",
                key=lambda x: pd.to_numeric(x,errors="coerce").fillna(-999),
                ascending=False).reset_index(drop=True)

        def tag_fn(row, idx):
            t = str(row.get("Trend",""))
            if "YÜKSELİYOR" in t: return "up"
            if "DÜŞÜYOR"    in t: return "dn"
            return "st"

        self._fill_tree(self.tree_trend, df, tag_fn=tag_fn)
        horses = ["Tümü"]+sorted(self.performlar.keys())
        self.trend_horse_cb["values"] = horses
        if len(horses)>1:
            self.trend_horse_var.set(horses[1])
            self._draw_trend_chart()

    def _draw_trend_chart(self):
        horse = self.trend_horse_var.get()
        cv    = self.cv_trend; cv.delete("all")
        if not horse or horse=="Tümü" or horse not in self.profiller: return

        races = sorted(self.profiller[horse].get("races",[]),
                       key=lambda r: parse_date_key(r.get("tarih","")))[-10:]
        data  = []
        for r in races:
            d = derece_to_sec(r.get("derece",""))
            try:
                msf = int(re.sub(r"[^\d]","",str(r.get("msf","") or "")))
                h   = msf/d if d and d>0 else None
                if h: data.append((r.get("tarih",""), round(h,3)))
            except: pass

        W = cv.winfo_width() or 450; H = cv.winfo_height() or 380
        if len(data) < 2:
            cv.create_text(W//2,H//2,text="Yeterli veri yok",fill=DIM,font=F_M); return

        PL,PR,PT,PB = 55,20,36,40
        vals = [v for _,v in data]
        mn,mx = min(vals),max(vals); rng = max(mx-mn,0.05)
        xs = (W-PL-PR)/max(len(data)-1,1)

        cv.create_text(W//2,18,
                       text=f"{horse}  —  Koşu Hız Trendi (m/s)",
                       fill=TEXT, font=F_S)

        for frac in [0,0.25,0.5,0.75,1.0]:
            val = mn+frac*rng; y = PT+(1-frac)*(H-PT-PB)
            cv.create_line(PL,y,W-PR,y,fill=BORDER,dash=(2,5))
            cv.create_text(PL-5,y,text=f"{val:.2f}",fill=DIM,font=F_XS,anchor="e")

        pts = []
        for i,(tarih,v) in enumerate(data):
            x = PL+i*xs; y = PT+(1-(v-mn)/rng)*(H-PT-PB)
            pts.append((x,y,v,tarih))

        for i in range(len(pts)-1):
            col = GREEN if pts[i+1][2]>pts[i][2] else RED
            cv.create_line(pts[i][0],pts[i][1],
                           pts[i+1][0],pts[i+1][1],
                           fill=col, width=2, smooth=True)
        for x,y,v,t in pts:
            cv.create_oval(x-4,y-4,x+4,y+4,fill=BLUE,outline=BG)
            cv.create_text(x,H-PB+12,text=t[-5:],
                           fill=DIM,font=F_XS,angle=30,anchor="nw")
            cv.create_text(x,y-10,text=f"{v:.2f}",
                           fill=TEXT,font=F_XS)
        cv.create_line(PL,PT,PL,H-PB,fill=DIM)
        cv.create_line(PL,H-PB,W-PR,H-PB,fill=DIM)

    # ── Karşılaştırma Tab ────────────────────────────────

    def _update_karsi_tab(self):
        if not self.sel_kosu: return
        atlar = self.sel_kosu.get("atlar",[])
        rows  = []
        for at in atlar:
            adi = at.get("at","")
            g   = self.galop_an.get(adi,{})
            s   = self.stiller.get(adi,{})
            p   = self.performlar.get(adi,{})
            rows.append({
                "No":         at.get("no",""),
                "At":         adi,
                "En_Iyi_400": g.get("en_iyi_400","—"),
                "Son_Galop":  str(g.get("gun_fark","—"))+"g" if g.get("gun_fark") is not None else "—",
                "Stil":       s.get("stil","—"),
                "Ilk3_%":     s.get("ilk3_pct","—"),
                "Son5":       s.get("son5","—"),
                "Trend":      p.get("trend","—"),
                "Trend_Skor": p.get("trend_skor","—"),
                "Taki":       at.get("taki",""),
                "AGF":        at.get("agf",""),
            })
        df = pd.DataFrame(rows)

        def tag_fn(row, idx):
            t = str(row.get("Trend",""))
            if "YÜKSELİYOR" in t: return "up"
            if "DÜŞÜYOR"    in t: return "dn"
            s = str(row.get("Stil",""))
            if "ÖNDEN" in s: return "g1"
            if "ORTADAN" in s: return "g2"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_karsi, df, tag_fn=tag_fn)
        self.after(100, self._draw_karsi_chart)

    def _draw_karsi_chart(self):
        """Basit çizgi karşılaştırma grafiği — ilk 8 at."""
        cv = self.cv_karsi; cv.delete("all")
        W  = cv.winfo_width() or 460; H = cv.winfo_height() or 380
        if not self.galop_an or W < 80: return

        items = sorted(
            [(at, d.get("en_iyi_400")) for at,d in self.galop_an.items()
             if d.get("en_iyi_400")],
            key=lambda x: x[1]
        )[:8]
        if not items: return

        PL,PR,PT,PB = 50,150,36,40
        vals = [v for _,v in items]
        mn,mx = min(vals),max(vals); rng=max(mx-mn,0.5)
        ys = (H-PT-PB)/max(len(items)-1,1)

        cv.create_text(W//2,18,text="400m Sıralama (en hızlı üstte)",
                       fill=TEXT,font=F_S)

        for i,(at,val) in enumerate(items):
            y    = PT + i*ys
            frac = (val-mn)/rng if rng>0 else 0.5
            bar_w= int(frac*(W-PL-PR-10))
            col  = LINE_C[i%len(LINE_C)]

            cv.create_rectangle(PL, y-10, PL+max(bar_w,4), y+10,
                                 fill=col, outline=BG)
            cv.create_text(PL+max(bar_w,4)+5, y,
                           text=f"{val:.2f}s", fill=col, font=F_XS, anchor="w")
            # İsim
            gun = self.galop_an.get(at,{}).get("gun_fark","")
            gun_txt = f" ({gun}g)" if gun is not None else ""
            cv.create_text(PL-5, y,
                           text=at[:14]+gun_txt, fill=TEXT, font=F_XS, anchor="e")

        cv.create_line(PL,PT-15,PL,H-PB,fill=DIM)

    # ── Tab: Takip Atları ─────────────────────────────────

    def _build_takip_tab(self, parent):
        # Üst filtreler
        flt = tk.Frame(parent, bg=BG)
        flt.pack(fill="x", padx=8, pady=(8,4))

        tk.Label(flt, text="Min Hız İndeksi:", font=F_S, bg=BG, fg=DIM).pack(side="left")
        self.takip_hiz_var = tk.StringVar(value="10")
        ttk.Combobox(flt, textvariable=self.takip_hiz_var,
                     values=["0","5","10","20","30","50"],
                     state="readonly", width=5, font=F_N).pack(side="left", padx=4)

        tk.Label(flt, text="Max Bitiş Sırası:", font=F_S, bg=BG, fg=DIM
                 ).pack(side="left", padx=(16,0))
        self.takip_sira_var = tk.StringVar(value="5")
        ttk.Combobox(flt, textvariable=self.takip_sira_var,
                     values=["3","4","5","6","8","Tümü"],
                     state="readonly", width=5, font=F_N).pack(side="left", padx=4)

        tk.Label(flt, text="Min Katılımcı:", font=F_S, bg=BG, fg=DIM
                 ).pack(side="left", padx=(16,0))
        self.takip_kati_var = tk.StringVar(value="6")
        ttk.Combobox(flt, textvariable=self.takip_kati_var,
                     values=["4","5","6","7","8","10"],
                     state="readonly", width=5, font=F_N).pack(side="left", padx=4)

        tk.Button(flt, text="🔍 Filtrele", command=self._update_takip,
                  bg=BLUE, fg=TEXT, font=F_S, relief="flat",
                  padx=10, pady=5).pack(side="left", padx=12)

        tk.Label(flt,
                 text="İyi koşup kazanamayan, form oluşturan, takip edilmesi gereken atlar",
                 font=F_XS, bg=BG, fg=TEAL).pack(side="left")

        # Podium kartları
        self.takip_cards = tk.Frame(parent, bg=BG)
        self.takip_cards.pack(fill="x", padx=8, pady=(0,6))

        # Orta: tablo + grafik
        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        tk.Label(lp, text="Takip Listesi — En Güçlü Performans Üstte",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.tree_takip = self._make_tree(lp)

        rp = tk.Frame(mid, bg=BG, width=380)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Takip Skoru Grafiği",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_takip = tk.Canvas(rp, bg=PANEL,
                                   highlightthickness=1, highlightbackground=BORDER)
        self.cv_takip.pack(fill="both", expand=True)
        self.cv_takip.bind("<Configure>", lambda e: self._draw_takip_chart())

    def _compute_takip_skor(self, at_adi: str, profil: dict) -> dict | None:
        """
        Bir atın 'takip edilmesi gereken at' skorunu hesapla.
        
        Kriter:
        1. Son N koşuda iyi hız ama düşük ödül (handikap yükü yüksek veya şanssız)
        2. Koşu stili oturmuş (stabil)
        3. Pozitif veya stabil trend
        4. Son koşuda belirli sıra içinde bitirmiş (ama 1. olmamış)
        5. Hız indeksi pozitif (galop derecesi iyi)
        
        Returns: None if not worth tracking
        """
        races = sorted(
            profil.get("races", []),
            key=lambda r: parse_date_key(r.get("tarih","")),
            reverse=True
        )[:5]  # son 5 koşu

        if not races:
            return None

        # --- Hız skorları ---
        hiz_skorlari = []
        for r in races:
            m = re.search(r"\(?([+-]?\d+)\)?", str(r.get("hiz","") or ""))
            if m:
                try: hiz_skorlari.append(int(m.group(1)))
                except: pass

        if not hiz_skorlari:
            return None

        ort_hiz = sum(hiz_skorlari) / len(hiz_skorlari)

        # Minimum hız filtresi
        try:
            min_hiz = int(self.takip_hiz_var.get())
        except:
            min_hiz = 10
        if ort_hiz < min_hiz:
            return None

        # --- Bitiş sıraları ---
        siralar = []
        for r in races:
            try:
                s = int(re.sub(r"[^\d]","", str(r.get("sira","") or "")))
                if 0 < s <= 30: siralar.append(s)
            except: pass

        if not siralar:
            return None

        ort_sira = sum(siralar) / len(siralar)
        son_sira = siralar[0]

        # Max bitiş sırası filtresi
        try:
            max_sira = int(self.takip_sira_var.get()) if self.takip_sira_var.get() != "Tümü" else 99
        except:
            max_sira = 5
        if son_sira > max_sira:
            return None

        # 1. olmamışsa daha değerli (henüz kazanmamış form atı)
        hic_birinci = any(s == 1 for s in siralar)

        # --- Trend ---
        trend = self.performlar.get(at_adi, {}).get("trend_skor", 0) or 0

        # --- Galop tazeliği ---
        galop = self.galop_an.get(at_adi, {})
        gun_fark = galop.get("gun_fark")
        taze_bonus = 0
        if gun_fark is not None:
            if gun_fark <= 7:  taze_bonus = 15
            elif gun_fark <= 14: taze_bonus = 8

        # --- Takip Skoru ---
        # Hız yüksek + sıra makul + trend pozitif + taze = yüksek skor
        skor = (
            ort_hiz * 0.5           +   # hız indeksi
            max(0, (6 - ort_sira) * 8) + # ortalama sıra (iyi sıra bonus)
            trend * 20              +   # yükseliş trendi
            taze_bonus              +   # galop tazeliği
            (10 if not hic_birinci else -5)  # henüz kazanmamış = form birikimi
        )

        # Neden takip edilmeli açıklaması
        nedenler = []
        if ort_hiz >= 30: nedenler.append(f"Yüksek hız ({ort_hiz:.0f})")
        if trend > 0.1:   nedenler.append("Yükselen trend")
        if taze_bonus > 0: nedenler.append(f"Taze galop ({gun_fark}g)")
        if not hic_birinci and son_sira <= 3:
            nedenler.append("İlk 3 formda, henüz 1. olmadı")
        if ort_sira <= 3:  nedenler.append(f"Ort.sıra {ort_sira:.1f}")

        # Son koşu özeti
        son_kosu = races[0]

        return {
            "At":           at_adi,
            "Takip_Skor":   round(skor, 1),
            "Son_Sira":     son_sira,
            "Ort_Sira":     round(ort_sira, 1),
            "Son_Hiz_Ind":  hiz_skorlari[0] if hiz_skorlari else "—",
            "Ort_Hiz_Ind":  round(ort_hiz, 1),
            "Trend":        self.performlar.get(at_adi, {}).get("trend", "—"),
            "Son_Galop":    f"{gun_fark}g" if gun_fark is not None else "—",
            "Son_Tarih":    son_kosu.get("tarih",""),
            "Son_Msf":      son_kosu.get("msf",""),
            "Son_Pist":     son_kosu.get("pist",""),
            "Kazandimi":    "✗ Hayır" if not hic_birinci else "✓ Evet",
            "Neden":        "  •  ".join(nedenler) if nedenler else "—",
            "_skor_raw":    skor,
        }

    def _update_takip(self):
        """Takip atlarını hesapla ve tabloyu güncelle."""
        if not self.profiller:
            return

        sonuclar = []
        for at_adi, profil in self.profiller.items():
            r = self._compute_takip_skor(at_adi, profil)
            if r:
                sonuclar.append(r)

        if not sonuclar:
            self._st("Filtre kriterlerine uyan takip atı bulunamadı.")
            return

        # Skora göre sırala
        sonuclar.sort(key=lambda x: x["_skor_raw"], reverse=True)

        # Podium
        self._draw_takip_podium(sonuclar[:3])

        # Tablo
        show_cols = ["At","Takip_Skor","Son_Sira","Ort_Sira",
                     "Son_Hiz_Ind","Ort_Hiz_Ind","Trend","Son_Galop",
                     "Son_Tarih","Son_Msf","Kazandimi","Neden"]
        df = pd.DataFrame([{k:v for k,v in r.items() if not k.startswith("_")}
                           for r in sonuclar])

        def tag_fn(row, idx):
            if idx == 0: return "g1"
            if idx == 1: return "g2"
            if idx == 2: return "g3"
            t = str(row.get("Trend",""))
            if "YÜKSELİYOR" in t: return "up"
            if "DÜŞÜYOR"    in t: return "dn"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_takip,
                        df[[c for c in show_cols if c in df.columns]],
                        tag_fn=tag_fn)

        self._takip_data = sonuclar
        self.after(100, self._draw_takip_chart)
        self._st(f"✓ {len(sonuclar)} takip atı bulundu")

    def _draw_takip_podium(self, top3):
        for w in self.takip_cards.winfo_children():
            w.destroy()
        if not top3: return

        tk.Label(self.takip_cards, text="⭐ En Güçlü Takip Atları",
                 font=F_M, bg=BG, fg=TEXT).pack(side="left", padx=(0,16))

        colors  = [GOLD, SILVER, BRONZE]
        medals  = ["🥇","🥈","🥉"]
        for i, r in enumerate(top3):
            c = tk.Frame(self.takip_cards, bg=CARD,
                         highlightthickness=2, highlightbackground=colors[i],
                         padx=14, pady=8)
            c.pack(side="left", padx=(0,10))
            tk.Label(c, text=f"{medals[i]} {r['At']}",
                     font=F_M, bg=CARD, fg=TEXT).pack()
            tk.Label(c, text=f"Skor: {r['Takip_Skor']}",
                     font=("Segoe UI",12,"bold"), bg=CARD, fg=colors[i]).pack()
            tk.Label(c, text=f"Son: {r['Son_Sira']}. | Ort: {r['Ort_Sira']} | Hız: {r['Son_Hiz_Ind']}",
                     font=F_XS, bg=CARD, fg=DIM).pack(pady=(2,0))
            neden = str(r.get("Neden",""))[:45]
            tk.Label(c, text=neden,
                     font=F_XS, bg=CARD, fg=TEAL).pack(pady=(1,0))

    def _draw_takip_chart(self):
        cv = self.cv_takip; cv.delete("all")
        W  = cv.winfo_width() or 380; H = cv.winfo_height() or 420
        if not hasattr(self,"_takip_data") or not self._takip_data or W < 80:
            return

        data = self._takip_data[:12]  # en fazla 12 at
        PL,PR,PT,PB = 50,12,40,65
        skorlar = [r["_skor_raw"] for r in data]
        mn = max(0, min(skorlar) - 5)
        mx = max(skorlar) + 5
        rng= max(mx - mn, 1)
        n  = len(data)
        bw = max(14, int((W-PL-PR)/n) - 4)
        xs = (W-PL-PR) / n

        cv.create_text(W//2, 20,
                       text="Takip Skoru (yüksek = öncelikli izle)",
                       fill=TEXT, font=F_S)

        for frac in [0, 0.25, 0.5, 0.75, 1.0]:
            val = mn + frac * rng
            y   = PT + (1-frac) * (H-PT-PB)
            cv.create_line(PL, y, W-PR, y, fill=BORDER, dash=(2,5))
            cv.create_text(PL-5, y, text=f"{val:.0f}",
                           fill=DIM, font=F_XS, anchor="e")

        for i, r in enumerate(data):
            skor = r["_skor_raw"]
            frac = (skor - mn) / rng
            bh   = max(4, int(frac * (H-PT-PB)))
            x0   = PL + i*xs + (xs-bw)/2
            x1   = x0 + bw
            y1   = H - PB; y0 = y1 - bh

            # Renk: kazanmamış + yüksek skor = altın
            if i == 0:               col = GOLD
            elif i == 1:             col = SILVER
            elif i == 2:             col = BRONZE
            elif r["Kazandimi"] == "✗ Hayır": col = TEAL
            else:                    col = BLUE

            cv.create_rectangle(x0, y0, x1, y1, fill=col, outline=BG)
            cv.create_text((x0+x1)/2, y0-5,
                           text=f"{skor:.0f}", fill=col, font=F_XS)
            # Son sıra küçük etiket
            cv.create_text((x0+x1)/2, y1+4,
                           text=f"{r['Son_Sira']}.", fill=DIM, font=F_XS)
            # At adı
            cv.create_text((x0+x1)/2, H-PB+14,
                           text=r["At"][:9],
                           fill=TEXT, font=F_XS, angle=40, anchor="nw")

        cv.create_line(PL, PT, PL, H-PB, fill=DIM)
        cv.create_line(PL, H-PB, W-PR, H-PB, fill=DIM)

        # Legend
        for col, lbl, x in [(TEAL,"Henüz kazanmadı",PL),
                             (BLUE,"Kazandı",        PL+110)]:
            cv.create_rectangle(x, H-PB+48, x+10, H-PB+58, fill=col, outline="")
            cv.create_text(x+13, H-PB+53, text=lbl, fill=col,
                           font=F_XS, anchor="w")

    # ── Tab: Son 2 Yarış Hız ─────────────────────────────

    def _build_son2hiz_tab(self, parent):
        tk.Label(parent,
                 text=("Hız = Mesafe ÷ Derece (m/s)  •  Son 2 koşu karşılaştırması  "
                       "•  Yeşil = hızlandı  •  Kırmızı = yavaşladı"),
                 font=F_XS, bg=BG, fg=DIM).pack(anchor="w", padx=8, pady=(8,4))

        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        # Sol: tablo
        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0,6))
        tk.Label(lp, text="At Bazında Son 2 Yarış Hız Analizi",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.tree_s2h = self._make_tree(lp)

        # Sağ: bar karşılaştırma grafiği
        rp = tk.Frame(mid, bg=BG, width=400)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Hız Karşılaştırması (m/s)",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_s2h = tk.Canvas(rp, bg=PANEL,
                                 highlightthickness=1, highlightbackground=BORDER)
        self.cv_s2h.pack(fill="both", expand=True)
        self.cv_s2h.bind("<Configure>", lambda e: self._draw_s2h_chart())

    def _update_son2hiz(self):
        """Her at için son 2 yarışın hız analizini hesapla ve göster."""
        if not self.profiller: return

        rows = []
        for at_adi, profil in self.profiller.items():
            races = sorted(
                profil.get("races", []),
                key=lambda r: parse_date_key(r.get("tarih","")),
                reverse=True
            )
            # Derece ve mesafesi olan ilk 2 yarışı al
            valid = []
            for r in races:
                d = derece_to_sec(r.get("derece",""))
                try:
                    m = int(re.sub(r"[^\d]","", str(r.get("msf","") or "")))
                except: m = 0
                if d and m > 0:
                    h = round(m / d, 3)
                    valid.append({
                        "tarih":  r.get("tarih",""),
                        "msf":    m,
                        "pist":   r.get("pist",""),
                        "sira":   r.get("sira",""),
                        "derece": r.get("derece",""),
                        "hiz":    h,
                        "jokey":  r.get("jokey",""),
                    })
                if len(valid) == 2:
                    break

            if not valid:
                continue

            son1 = valid[0]  # en yeni
            son2 = valid[1] if len(valid) > 1 else None

            fark     = round(son1["hiz"] - son2["hiz"], 3) if son2 else None
            fark_pct = round(fark / son2["hiz"] * 100, 1)  if son2 and son2["hiz"] else None

            if fark is not None:
                if fark > 0.05:    trend = "🟢 HIZLANDI"
                elif fark < -0.05: trend = "🔴 YAVAŞLADI"
                else:              trend = "🟡 STABİL"
            else:
                trend = "—"

            row = {
                "At":            at_adi,
                "Trend":         trend,
                "Son1_Tarih":    son1["tarih"],
                "Son1_Msf":      son1["msf"],
                "Son1_Pist":     son1["pist"],
                "Son1_Sira":     son1["sira"],
                "Son1_Derece":   son1["derece"],
                "Son1_Hiz(m/s)": son1["hiz"],
                "Son2_Tarih":    son2["tarih"] if son2 else "—",
                "Son2_Msf":      son2["msf"]   if son2 else "—",
                "Son2_Pist":     son2["pist"]  if son2 else "—",
                "Son2_Sira":     son2["sira"]  if son2 else "—",
                "Son2_Derece":   son2["derece"]if son2 else "—",
                "Son2_Hiz(m/s)": son2["hiz"]  if son2 else "—",
                "Fark(m/s)":     fark          if fark is not None else "—",
                "Fark_%":        fark_pct      if fark_pct is not None else "—",
            }
            rows.append(row)

        if not rows: return

        df = pd.DataFrame(rows)
        # En çok hızlanan üstte
        df = df.sort_values(
            "Fark(m/s)",
            key=lambda x: pd.to_numeric(x, errors="coerce").fillna(-999),
            ascending=False
        ).reset_index(drop=True)

        def tag_fn(row, idx):
            t = str(row.get("Trend",""))
            if "HIZLANDI" in t: return "up"
            if "YAVAŞLADI" in t: return "dn"
            if "STABİL"   in t: return "st"
            return "odd" if idx%2==0 else "ev"

        self._fill_tree(self.tree_s2h, df, tag_fn=tag_fn)

        # Grafik için cache
        self._s2h_data = rows
        self.after(100, self._draw_s2h_chart)

    def _draw_s2h_chart(self):
        """Son 2 yarış hız çift bar grafiği."""
        cv = self.cv_s2h; cv.delete("all")
        W  = cv.winfo_width() or 400; H = cv.winfo_height() or 420
        if not hasattr(self,"_s2h_data") or not self._s2h_data or W < 80: return

        data = [r for r in self._s2h_data
                if isinstance(r.get("Son1_Hiz(m/s)"), float)]
        if not data: return

        # Hız değerlerini topla — ölçek için
        all_hiz = []
        for r in data:
            all_hiz.append(r["Son1_Hiz(m/s)"])
            if isinstance(r.get("Son2_Hiz(m/s)"), float):
                all_hiz.append(r["Son2_Hiz(m/s)"])
        if not all_hiz: return

        PL,PR,PT,PB = 52,16,48,50
        mn = min(all_hiz) - 0.2
        mx = max(all_hiz) + 0.2
        rng= max(mx - mn, 0.1)
        n  = len(data)
        grp_w = (W - PL - PR) / n
        bar_w = max(8, int(grp_w * 0.35))

        cv.create_text(W//2, 20,
                       text="Son 2 Yarış Hız Karşılaştırması (m/s)",
                       fill=TEXT, font=F_S)

        # Grid
        for frac in [0, 0.25, 0.5, 0.75, 1.0]:
            val = mn + frac * rng
            y   = PT + (1-frac) * (H-PT-PB)
            cv.create_line(PL, y, W-PR, y, fill=BORDER, dash=(2,5))
            cv.create_text(PL-5, y, text=f"{val:.2f}",
                           fill=DIM, font=F_XS, anchor="e")

        for i, row in enumerate(data):
            cx   = PL + (i + 0.5) * grp_w
            h1   = row["Son1_Hiz(m/s)"]
            h2   = row.get("Son2_Hiz(m/s)")
            fark = row.get("Fark(m/s)")

            # Renk: hızlandıysa yeşil, yavaşladıysa kırmızı
            if isinstance(fark, float):
                col1 = GREEN if fark >= 0 else RED
            else:
                col1 = BLUE
            col2 = SILVER

            # Bar 1 (son yarış)
            y1_top = PT + (1 - (h1-mn)/rng) * (H-PT-PB)
            y_bot  = PT + (H-PT-PB)
            cv.create_rectangle(cx - bar_w - 2, y1_top,
                                 cx - 2, y_bot,
                                 fill=col1, outline=BG)
            cv.create_text(cx - bar_w//2 - 2, y1_top - 4,
                           text=f"{h1:.2f}", fill=col1, font=F_XS)

            # Bar 2 (önceki yarış)
            if isinstance(h2, float):
                y2_top = PT + (1 - (h2-mn)/rng) * (H-PT-PB)
                cv.create_rectangle(cx + 2, y2_top,
                                     cx + bar_w + 2, y_bot,
                                     fill=col2, outline=BG)
                cv.create_text(cx + bar_w//2 + 2, y2_top - 4,
                               text=f"{h2:.2f}", fill=col2, font=F_XS)

            # Fark oku
            if isinstance(fark, float) and isinstance(h2, float):
                ok = "▲" if fark > 0 else "▼"
                col_ok = GREEN if fark > 0 else RED
                cv.create_text(cx, y_bot - 4,
                               text=f"{ok}{abs(fark):.3f}",
                               fill=col_ok, font=F_XS)

            # At adı
            cv.create_text(cx, H-PB+14,
                           text=row["At"][:9],
                           fill=TEXT, font=F_XS, angle=38, anchor="nw")

        # Eksen
        cv.create_line(PL, PT, PL, H-PB, fill=DIM)
        cv.create_line(PL, H-PB, W-PR, H-PB, fill=DIM)

        # Legend
        for col, lbl, x in [(GREEN,"Son Yarış (hızlandı)", PL),
                             (RED,  "Son Yarış (yavaşladı)", PL+120),
                             (SILVER,"Önceki Yarış",         PL+240)]:
            cv.create_rectangle(x, H-PB+38, x+10, H-PB+48, fill=col, outline="")
            cv.create_text(x+13, H-PB+43, text=lbl, fill=col, font=F_XS, anchor="w")

    # ── Tab: Senaryo ─────────────────────────────────────

    def _build_senaryo_tab(self, parent):
        # ── Üst kontrol ──────────────────────────────────
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(fill="x", padx=8, pady=(8,4))

        tk.Button(ctrl, text="▶  OYNAT",
                  command=self._oynat_senaryo,
                  bg=ACCENT, fg=TEXT, font=F_M, relief="flat",
                  cursor="hand2", padx=14, pady=7
                  ).pack(side="left")
        tk.Button(ctrl, text="⏹",
                  command=self._durdur_senaryo,
                  bg="#2A2A2A", fg=TEXT, font=F_S, relief="flat",
                  cursor="hand2", padx=8, pady=7
                  ).pack(side="left", padx=4)
        tk.Button(ctrl, text="↺  Başa Al",
                  command=lambda: self._render_frame(0.0),
                  bg="#1E3048", fg=TEXT, font=F_S, relief="flat",
                  cursor="hand2", padx=8, pady=7
                  ).pack(side="left", padx=4)

        tk.Label(ctrl, text="Hız:", font=F_XS, bg=BG, fg=DIM).pack(side="left", padx=(16,2))
        self.anim_hiz = tk.IntVar(value=50)
        ttk.Scale(ctrl, from_=10, to=120, variable=self.anim_hiz,
                  orient="horizontal", length=90).pack(side="left")

        self.sn_info = tk.StringVar(value="Analiz çalıştırınca senaryo oluşur.")
        tk.Label(ctrl, textvariable=self.sn_info,
                 font=F_XS, bg=BG, fg=TEAL).pack(side="left", padx=16)

        # ── Orta alan: animasyon (sol) + pozisyon tablosu (sağ) ──
        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8, pady=(4,4))

        # Sol: pist animasyonu
        left = tk.Frame(mid, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,6))

        tk.Label(left, text="Yarış Pisti — Animasyon",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))
        self.cv_sen = tk.Canvas(left, bg="#0A1A0A",
                                highlightthickness=1, highlightbackground=BORDER)
        self.cv_sen.pack(fill="both", expand=True)
        self.cv_sen.bind("<Configure>", lambda e: self._draw_senaryo_static())

        # Sağ: split pozisyon tablosu
        right = tk.Frame(mid, bg=BG, width=420)
        right.pack(side="left", fill="both")
        right.pack_propagate(False)

        tk.Label(right, text="📍 Split Bazlı Pozisyon Tahmini",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0,4))

        # Treeview — sütunlar: At, 200m, 400m, 600m, Son200m, Bitiş
        tf = tk.Frame(right, bg=PANEL,
                      highlightthickness=1, highlightbackground=BORDER)
        tf.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(tf, orient="vertical")
        self.tree_sen = ttk.Treeview(tf, show="headings",
                                      yscrollcommand=vsb.set)
        vsb.config(command=self.tree_sen.yview)
        vsb.pack(side="right", fill="y")
        self.tree_sen.pack(fill="both", expand=True)

        split_cols = [
            ("No",     30),
            ("At",    110),
            ("Start",  45),
            ("200m",   45),
            ("400m",   45),
            ("600m",   45),
            ("800m",   45),
            ("Son200", 50),
            ("Bitiş",  45),
            ("Güç",    45),
        ]
        self.tree_sen["columns"] = [c for c,_ in split_cols]
        for col, w in split_cols:
            self.tree_sen.heading(col, text=col)
            self.tree_sen.column(col, width=w, anchor="center", minwidth=w)

        self.tree_sen.tag_configure("g1",  background="#1F3A12", foreground=GOLD)
        self.tree_sen.tag_configure("g2",  background="#112233", foreground=SILVER)
        self.tree_sen.tag_configure("g3",  background="#2A1A08", foreground=BRONZE)
        self.tree_sen.tag_configure("ond", background="#0F2210", foreground=GREEN)
        self.tree_sen.tag_configure("ger", background="#0F1A2A", foreground=BLUE)
        self.tree_sen.tag_configure("odd", background="#162030")
        self.tree_sen.tag_configure("ev",  background=PANEL)

        # ── Alt: yarış yorumu (ince) ──────────────────────
        yt = tk.Frame(parent, bg=BG)
        yt.pack(fill="x", padx=8, pady=(0,6))
        tk.Label(yt, text="Yarış Yorumu:", font=F_S, bg=BG, fg=DIM).pack(side="left")
        self.txt_sen = tk.Text(yt, bg=PANEL, fg=TEXT, font=F_XS,
                               height=5, relief="flat",
                               highlightthickness=1, highlightbackground=BORDER,
                               state="disabled", wrap="word")
        self.txt_sen.pack(fill="x", expand=True, padx=(6,0))

        # Animasyon state
        self._anim_running = False
        self._anim_frame   = 0

    # ── Senaryo Hesaplama ─────────────────────────────────

    def _compute_senaryo(self):
        """
        Her at için koşu boyunca tahmini pozisyonu hesapla.
        Splitler: start, 200m, 400m, 600m, (800m), son200m, finish
        Returns list of {at, stil, renkler, pozlar, yorum}
        """
        if not self.sel_kosu: return []
        atlar = self.sel_kosu.get("atlar", [])
        if not atlar: return []

        mesafe = 0
        try: mesafe = int(re.sub(r"[^\d]","",self.sel_kosu.get("mesafe","") or ""))
        except: pass

        result = []
        n_at   = len(atlar)

        for i, at in enumerate(atlar):
            adi   = at.get("at","")
            stil  = self.stiller.get(adi, {})
            galop = self.galop_an.get(adi, {})
            perf  = self.performlar.get(adi, {})
            son10 = at.get("son10", [])

            # ── Temel parametreler ──
            # Stil skoru: önden=1, orta=0, geriden=-1
            stil_txt = stil.get("stil","")
            if "ÖNDEN" in stil_txt:       stil_skor = 1.0
            elif "ORTADAN" in stil_txt:   stil_skor = 0.0
            else:                          stil_skor = -1.0

            # Hız kapasitesi (galop + performans)
            hiz_kap = 0.5
            en_iyi  = galop.get("en_iyi_400")
            if en_iyi:
                hiz_kap = max(0, min(1, (28.0 - en_iyi) / 6.0))
            gun_fark = galop.get("gun_fark")
            taze_mod = 1.0 if gun_fark is not None and gun_fark <= 7 else \
                       0.85 if gun_fark is not None and gun_fark <= 14 else 0.7

            trend_skor = perf.get("trend_skor", 0) or 0
            trend_mod  = 1.0 + min(0.15, max(-0.15, trend_skor * 0.1))

            # Son 3 form
            son3 = [s for s in son10[:3] if isinstance(s,int) and s>0]
            form_mod = 1.0
            if son3:
                ort = sum(son3)/len(son3)
                form_mod = max(0.7, min(1.2, 1.5 - ort*0.1))

            # Genel güç = hız × tazelik × trend × form
            guc = hiz_kap * taze_mod * trend_mod * form_mod

            # ── Pozisyon simülasyonu ──
            # Her split noktasında sıra tahmini (1=başta)
            # start_pos: önden koşanlar küçük sayı, kapıcılar büyük
            noise_seed = hash(adi) % 100 / 100.0  # at başına sabit gürültü
            start_pos = 1 + (1 - stil_skor) * (n_at/2 - 1) + noise_seed * 1.5
            start_pos = max(1, min(n_at, start_pos))

            # Koşunun ilerleyişinde güçlü at öne geçer
            # split_pct: 0=start, 0.3=erken, 0.6=orta, 1.0=bitiş
            def pos_at(pct):
                # Önden: erken iyi, sonda yorulabilir
                if stil_skor > 0.5:
                    early_bonus = -1.5 * guc
                    late_fade   = pct * 1.5 * (1 - guc)
                    p = start_pos + early_bonus + late_fade
                # Geriden: başta geride, sonda yükselir
                elif stil_skor < -0.3:
                    late_gain = -pct * 3.0 * guc
                    p = start_pos + late_gain
                # Ortadan
                else:
                    mid_gain = -pct * 1.5 * guc
                    p = start_pos + mid_gain

                return max(1.0, min(float(n_at), p))

            splits = [0.0, 0.15, 0.35, 0.55, 0.75, 0.90, 1.0]
            pozlar = [round(pos_at(s), 2) for s in splits]

            # Bitiş sırası
            finish = round(pozlar[-1])
            finish = max(1, min(n_at, finish))

            result.append({
                "at":      adi,
                "no":      at.get("no",""),
                "stil":    stil_txt or "?",
                "stil_skor": stil_skor,
                "guc":     round(guc, 3),
                "pozlar":  pozlar,
                "finish":  finish,
                "renk":    LINE_C[i % len(LINE_C)],
                "taki":    at.get("taki",""),
                "agf":     at.get("agf",""),
                "en_iyi_400": en_iyi,
                "gun_fark":   gun_fark,
                "trend":   perf.get("trend",""),
            })

        # Bitiş sıralarını normalize et (1..n eşsiz)
        result.sort(key=lambda x: x["pozlar"][-1])
        for rank, r in enumerate(result, 1):
            r["finish_rank"] = rank

        return result

    def _yorum_uret(self, senaryo: list, mesafe: int) -> str:
        """Senaryo verisiyle Türkçe yarış yorumu oluştur."""
        if not senaryo: return "Yeterli veri yok."

        lideri  = [r for r in senaryo if "ÖNDEN" in r["stil"]]
        kapici  = [r for r in senaryo if "GERİDEN" in r["stil"] or "KAPICI" in r["stil"]]
        tahmini = senaryo[0]  # bitiş sıralaması 1. tahmin

        lines = []

        # Pist yorumu
        if mesafe and mesafe <= 1200:
            lines.append(f"⚡ {mesafe}m sprint mesafesi — start hızı kritik, önden koşanlar avantajlı.")
        elif mesafe and mesafe >= 2000:
            lines.append(f"🏃 {mesafe}m uzun mesafe — geriden gelenler ve dayanıklılık ön plana çıkar.")
        else:
            lines.append(f"🎯 {mesafe}m orta mesafe — her stilden at şansına sahip.")

        # Lider tahmini
        lider_adlari = ", ".join(r["at"] for r in sorted(lideri, key=lambda x: x["guc"], reverse=True)[:3])
        if lider_adlari:
            lines.append(f"\n🟢 ÖNDEN KOŞACAKLAR: {lider_adlari}")
            lines.append("   Bu atlar start bandından ilk pozisyonu almaya çalışacak.")

        # Kapıcılar
        kap_adlari = ", ".join(r["at"] for r in sorted(kapici, key=lambda x: x["guc"], reverse=True)[:3])
        if kap_adlari:
            lines.append(f"\n🔵 GERİDEN YÜKSELECEKLER: {kap_adlari}")
            lines.append("   Son 400m'de pozisyon kazanımı bekleniyor.")

        # Tehlikeli atlar
        tehlikeli = [r for r in senaryo
                     if r["guc"] > 0.6 and r.get("gun_fark") is not None and r["gun_fark"] <= 7]
        if tehlikeli:
            t_adi = ", ".join(r["at"] for r in tehlikeli[:2])
            lines.append(f"\n⚠️  TEHLİKELİ ADAYLAR: {t_adi}")
            lines.append("   Hem taze hem güçlü galop — formda görünüyor.")

        # Sürpriz adaylar
        surpriz = [r for r in senaryo
                   if r.get("trend","") == "🟢 YÜKSELİYOR" and r["finish_rank"] <= 4]
        if surpriz:
            s_adi = ", ".join(r["at"] for r in surpriz[:2])
            lines.append(f"\n🚀 YÜKSELİŞ TRENDİ: {s_adi}")
            lines.append("   Son koşularda hız arttı — sürpriz yapabilir.")

        # Tahmini finalist
        top3 = [r["at"] for r in senaryo[:3]]
        lines.append(f"\n🏆 TAHMİNİ İLK 3: {' — '.join(top3)}")

        # Riskler
        riskler = []
        for r in senaryo:
            if r.get("gun_fark") is not None and r["gun_fark"] > 21:
                riskler.append(f"{r['at']} (son galop {r['gun_fark']}g önce)")
        if riskler:
            lines.append(f"\n⚫ HAZIRLIK SORUSU: {', '.join(riskler[:2])}")

        return "\n".join(lines)

    def _update_senaryo(self):
        """Analiz bittikten sonra senaryoyu hesapla, tabloyu ve yorumu doldur."""
        self._senaryo_data = self._compute_senaryo()
        mesafe = 0
        try: mesafe = int(re.sub(r"[^\d]","",self.sel_kosu.get("mesafe","") or ""))
        except: pass

        # ── Split pozisyon tablosu ────────────────────────
        self._fill_split_table()

        # ── Yarış yorumu ─────────────────────────────────
        yorum = self._yorum_uret(self._senaryo_data, mesafe)
        self.txt_sen.config(state="normal")
        self.txt_sen.delete("1.0","end")
        self.txt_sen.insert("end", yorum)
        self.txt_sen.config(state="disabled")

        # Statik çizim
        self._draw_senaryo_static()
        n = len(self._senaryo_data)
        self.sn_info.set(f"{n} at  —  ▶ Oynat  |  Sağda split pozisyon tablosu")

        # Sekmeye geç
        self.nb.select(7)

    def _fill_split_table(self):
        """Split bazlı pozisyon tahmin tablosunu doldur — bitiş sırasına göre sırala."""
        tree = self.tree_sen
        tree.delete(*tree.get_children())
        if not hasattr(self,"_senaryo_data") or not self._senaryo_data:
            return

        # Nokta etiketleri: [Start, 200m, 400m, 600m, 800m, Son200, Bitiş]
        split_pcts = [0.0, 0.15, 0.35, 0.55, 0.75, 0.90, 1.0]

        def interp(pozlar, pct):
            for i in range(len(split_pcts)-1):
                if split_pcts[i] <= pct <= split_pcts[i+1]:
                    t = (pct-split_pcts[i])/(split_pcts[i+1]-split_pcts[i])
                    return pozlar[i] + t*(pozlar[i+1]-pozlar[i])
            return pozlar[-1]

        # Bitiş sırasına göre sırala
        sorted_data = sorted(self._senaryo_data, key=lambda r: r["finish_rank"])

        for idx, r in enumerate(sorted_data):
            finish = r["finish_rank"]

            # Her split için tahmini pozisyon (1..n, yuvarlanmış)
            def pos(pct):
                v = interp(r["pozlar"], pct)
                return str(int(round(v)))

            guc_pct = f"%{int(r['guc']*100)}"

            vals = (
                r["no"],
                r["at"],
                pos(0.0),    # Start
                pos(0.15),   # 200m
                pos(0.35),   # 400m
                pos(0.55),   # 600m
                pos(0.75),   # 800m
                pos(0.90),   # Son 200m
                str(finish), # Bitiş
                guc_pct,
            )

            # Tag
            if finish == 1:   tag = "g1"
            elif finish == 2: tag = "g2"
            elif finish == 3: tag = "g3"
            elif "ÖNDEN" in r["stil"]:  tag = "ond"
            elif "GERİDEN" in r["stil"] or "KAPICI" in r["stil"]: tag = "ger"
            else: tag = "odd" if idx%2==0 else "ev"

            tree.insert("","end", values=vals, tags=(tag,))

    def _draw_senaryo_static(self):
        """Statik son durum çizimi (animasyon olmadan)."""
        if not hasattr(self,"_senaryo_data") or not self._senaryo_data:
            return
        self._render_frame(1.0)

    def _render_frame(self, pct: float):
        """
        pct: 0.0 (start) → 1.0 (finish)
        Her at için pct'ye göre interpolasyon yap ve pisti çiz.
        """
        cv = self.cv_sen
        cv.delete("all")
        W = cv.winfo_width()  or 900
        H = cv.winfo_height() or 400
        if W < 100 or H < 100: return

        data = self._senaryo_data
        n_at = len(data)

        # Pist arka planı
        PIST_TOP    = 60
        PIST_BOT    = H - 80
        LANE_H      = (PIST_BOT - PIST_TOP) / max(n_at, 1)
        PIST_LEFT   = 120
        PIST_RIGHT  = W - 160

        # Zemin
        cv.create_rectangle(PIST_LEFT, PIST_TOP,
                             PIST_RIGHT, PIST_BOT,
                             fill="#1A2A0A", outline=BORDER)

        # Şerit çizgileri
        for i in range(n_at + 1):
            y = PIST_TOP + i * LANE_H
            cv.create_line(PIST_LEFT, y, PIST_RIGHT, y,
                           fill="#2A3A1A", width=1)

        # Start + bitiş çizgisi
        cv.create_line(PIST_LEFT, PIST_TOP-5,
                       PIST_LEFT, PIST_BOT+5, fill=SILVER, width=2)
        cv.create_line(PIST_RIGHT, PIST_TOP-5,
                       PIST_RIGHT, PIST_BOT+5, fill=GOLD, width=3, dash=(5,3))

        # Mesafe etiketleri
        splits_pct  = [0.0, 0.15, 0.35, 0.55, 0.75, 0.90, 1.0]
        splits_lbl  = ["Start","200m","400m","600m","800m","Son200m","Bitiş"]
        mesafe = 0
        try: mesafe = int(re.sub(r"[^\d]","",self.sel_kosu.get("mesafe","") or ""))
        except: pass

        for sp, lbl in zip(splits_pct, splits_lbl):
            x = PIST_LEFT + sp * (PIST_RIGHT - PIST_LEFT)
            if sp > 0 and sp < 1:
                cv.create_line(x, PIST_TOP, x, PIST_BOT,
                               fill="#2A4A1A", dash=(3,6))
            cv.create_text(x, PIST_TOP - 12, text=lbl,
                           fill=DIM, font=F_XS, anchor="s")

        # Başlık
        sn_pct_txt = f"{int(pct*100)}%"
        kosu_txt = (f"{self.sel_kosu.get('no','')}. Koşu  "
                    f"{self.sel_kosu.get('mesafe','')}m {self.sel_kosu.get('pist','')}  "
                    f"— Senaryo  {sn_pct_txt}")
        cv.create_text(W//2, 20, text=kosu_txt,
                       fill=GOLD, font=F_M, anchor="center")

        # Splits indeksi için pct→pozisyon interpolasyonu
        def interp_pos(pozlar, pct):
            """7 noktalı pozisyon listesinden pct anındaki değeri interpole et."""
            n = len(splits_pct) - 1
            for i in range(n):
                if splits_pct[i] <= pct <= splits_pct[i+1]:
                    t = (pct - splits_pct[i]) / (splits_pct[i+1] - splits_pct[i])
                    return pozlar[i] + t * (pozlar[i+1] - pozlar[i])
            return pozlar[-1]

        # Her at çiz
        for r in data:
            pos  = interp_pos(r["pozlar"], pct)   # 1..n arası float
            col  = r["renk"]
            at   = r["at"]

            # Şerit y koordinatı (pos büyüdükçe aşağı → 1=en üst)
            lane_y = PIST_TOP + (pos - 0.5) * LANE_H

            # x koordinatı: pct → pist üzerinde konum
            x = PIST_LEFT + pct * (PIST_RIGHT - PIST_LEFT)

            # At simgesi (oval)
            R = max(8, int(LANE_H * 0.32))
            cv.create_oval(x-R*2, lane_y-R,
                           x+R*0.5, lane_y+R,
                           fill=col, outline=BG, width=1)

            # At adı sol tarafta (start öncesi)
            if pct < 0.05:
                cv.create_text(PIST_LEFT - 5, lane_y,
                               text=f"{r['no']}. {at[:12]}",
                               fill=col, font=F_XS, anchor="e")

            # İsim etiketi atın üzerinde
            cv.create_text(x - R*0.8, lane_y - R - 4,
                           text=at[:8],
                           fill=col, font=F_XS, anchor="s")

        # Sağda bitiş sıralaması (pct > 0.85 iken)
        if pct > 0.85:
            sorted_now = sorted(data, key=lambda r: interp_pos(r["pozlar"], pct))
            for rank, r in enumerate(sorted_now, 1):
                y_rank = PIST_BOT + 18 + (rank-1) * 0 # sıralamayı sağda yaz
                x_rank = PIST_RIGHT + 10
                col    = [GOLD, SILVER, BRONZE][rank-1] if rank <= 3 else DIM
                cv.create_text(x_rank, PIST_TOP + (rank-0.5) * LANE_H,
                               text=f"{rank}. {r['at'][:12]}",
                               fill=col, font=F_XS, anchor="w")

    # ── Animasyon ─────────────────────────────────────────

    def _oynat_senaryo(self):
        if not hasattr(self,"_senaryo_data") or not self._senaryo_data:
            messagebox.showwarning("Uyarı","Önce koşuyu analiz edin.")
            return
        self._anim_running = True
        self._anim_frame   = 0
        self._anim_step()

    def _durdur_senaryo(self):
        self._anim_running = False

    def _anim_step(self):
        if not self._anim_running: return
        TOTAL_FRAMES = 120
        pct = self._anim_frame / TOTAL_FRAMES
        self._render_frame(min(pct, 1.0))
        self._anim_frame += 1
        if self._anim_frame > TOTAL_FRAMES:
            self._anim_running = False
            self._render_frame(1.0)
            return
        delay = max(8, 130 - self.anim_hiz.get())
        self.after(delay, self._anim_step)

    # ── Tab: Trakus & Tempo ──────────────────────────────

    def _build_trakus_tab(self, parent):
        # Üst açıklama
        info_f = tk.Frame(parent, bg="#1A1A30")
        info_f.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(info_f,
                 text=("🏁  TRAKUS & TEMPO ANALİZİ  —  "
                       "TJK Trakus GPS verileri veya profil derecelerinden "
                       "seksiyonel hız, erken/geç pace, kapanış gücü ve "
                       "tempo profili hesaplanır."),
                 font=F_XS, bg="#1A1A30", fg=DIM, wraplength=1400,
                 justify="left", padx=8, pady=4).pack(fill="x")

        # Üst kontrol barı
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(fill="x", padx=8, pady=(6, 4))

        tk.Button(ctrl, text="📡  TJK TRAKUS ÇEK",
                  command=self._cek_tjk_trakus,
                  bg="#6C3483", fg=TEXT, font=F_M, relief="flat",
                  cursor="hand2", padx=14, pady=7).pack(side="left")

        tk.Button(ctrl, text="📊  PROFİLDEN TEMPO",
                  command=self._tempo_profilden,
                  bg=BLUE, fg=TEXT, font=F_S, relief="flat",
                  cursor="hand2", padx=10, pady=7).pack(side="left", padx=6)

        self.trakus_info = tk.StringVar(
            value="📡 TJK Trakus → split bazlı gerçek tempo  |  "
                  "📊 Profil → derece bazlı tahmin  |  "
                  "İlk önce bülteni çekip koşuyu analiz edin")
        tk.Label(ctrl, textvariable=self.trakus_info,
                 font=F_XS, bg=BG, fg=TEAL).pack(side="left", padx=12)

        # Koşu seçici (TJK verileri için)
        self.trakus_kosu_var = tk.StringVar(value="Tümü")
        tk.Label(ctrl, text="Koşu:", font=F_XS, bg=BG, fg=DIM
                 ).pack(side="left", padx=(16, 2))
        self.trakus_kosu_cb = ttk.Combobox(
            ctrl, textvariable=self.trakus_kosu_var,
            state="readonly", width=10, font=F_N)
        self.trakus_kosu_cb.pack(side="left", padx=4)
        self.trakus_kosu_cb.bind("<<ComboboxSelected>>",
                                  lambda e: self._refresh_trakus_tab())

        # Podium
        self.trakus_cards = tk.Frame(parent, bg=BG)
        self.trakus_cards.pack(fill="x", padx=8, pady=(0, 6))

        # Orta: tablo + grafik
        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        # Sol: tempo tablosu
        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(lp, text="Tempo Analizi — Seksiyonel Hız & Pace Karşılaştırması",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 4))
        self.tree_trakus = self._make_tree(lp)

        # Sağ: grafik
        rp = tk.Frame(mid, bg=BG, width=480)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Seksiyonel Hız Profili (m/s) — At Bazlı Çizgi Grafiği",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 4))
        self.cv_trakus = tk.Canvas(rp, bg=PANEL,
                                    highlightthickness=1,
                                    highlightbackground=BORDER)
        self.cv_trakus.pack(fill="both", expand=True)
        self.cv_trakus.bind("<Configure>",
                             lambda e: self._draw_trakus_chart())

        # Alt: detay metin (daha geniş)
        bt = tk.Frame(parent, bg=BG)
        bt.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bt, text="Tempo Raporu:", font=F_S, bg=BG, fg=GOLD
                 ).pack(side="left")
        self.txt_tempo = tk.Text(bt, bg=PANEL, fg=TEXT, font=F_XS,
                                  height=12, relief="flat",
                                  highlightthickness=1,
                                  highlightbackground=BORDER,
                                  state="disabled", wrap="word")
        self.txt_tempo.pack(fill="x", expand=True, padx=(6, 0))

    # ── TJK Trakus Çek ─────────────────────────────────────

    def _cek_tjk_trakus(self):
        if not self._ready:
            messagebox.showwarning("Bekle", "Sistem hazırlanıyor.")
            return
        if not BS4:
            messagebox.showerror("Hata", "beautifulsoup4 gerekli.")
            return
        tarih = self.e_tarih.get().strip()
        sehir = self.sehir_var.get().strip()
        if not tarih or not sehir:
            messagebox.showwarning("Uyarı", "Tarih ve şehir seçin.")
            return
        threading.Thread(target=self._tjk_worker,
                         args=(tarih, sehir), daemon=True).start()

    def _tjk_worker(self, tarih, sehir):
        self.prog.start(10)
        self._st(f"TJK Trakus çekiliyor: {tarih} {sehir}…")
        try:
            kosular = scrape_tjk_sonuclar(tarih, sehir)
            self.tjk_trakus = kosular
            self._st(f"✓ TJK: {len(kosular)} koşu Trakus verisi çekildi")

            # Tempo analizi
            self._st("Tempo analizi yapılıyor…")
            self.tempo_an = analiz_tempo(kosular, self.profiller or None)
            self._st(f"✓ Tempo analizi: {len(self.tempo_an)} at")

            self.after(0, self._on_trakus_done)
        except Exception as e:
            self.after(0, lambda e2=str(e):
                       messagebox.showerror(
                           "TJK Hatası",
                           f"TJK Trakus çekilemedi:\n\n{e2}\n\n"
                           f"Alternatif: 'Profilden Tempo' butonunu "
                           f"kullanarak mevcut profillerden tempo "
                           f"tahmini alabilirsiniz."))
            self._st(f"TJK hatası: {e}")
        finally:
            self.prog.stop()

    def _tempo_profilden(self):
        """Mevcut profil verilerinden tempo analizi üret."""
        if not self.profiller:
            messagebox.showwarning(
                "Veri Yok",
                "Önce bir koşuyu analiz edin (profil verisi gerekli).")
            return
        self._st("Profilden tempo analizi yapılıyor…")
        self.tempo_an = analiz_tempo([], self.profiller)
        self._st(f"✓ Tempo analizi (profil): {len(self.tempo_an)} at")
        self._on_trakus_done()

    def _on_trakus_done(self):
        """Trakus/Tempo verisi gelince tabloyu güncelle."""
        # Koşu combobox
        if self.tjk_trakus:
            vals = ["Tümü"] + [f"{k['kosu_no']}. Koşu"
                                for k in self.tjk_trakus]
            self.trakus_kosu_cb["values"] = vals
            self.trakus_kosu_var.set("Tümü")

        self._refresh_trakus_tab()

        # Trakus sekmesine geç (son sekme = index 9)
        try:
            self.nb.select(9)
        except Exception:
            pass

    def _refresh_trakus_tab(self):
        """Tempo tablosunu ve grafiğini güncelle."""
        if not self.tempo_an:
            return

        # Koşu filtresi
        secim = self.trakus_kosu_var.get()
        if secim and secim not in ("Tümü",):
            m = re.search(r"(\d+)", secim)
            if m:
                kno = int(m.group(1))
                filtered = {k: v for k, v in self.tempo_an.items()
                            if v.get("kosu_no") == kno}
            else:
                filtered = self.tempo_an
        else:
            filtered = self.tempo_an

        # Tablo satırları — detaylı sütunlar
        rows = []
        for at, t in filtered.items():
            # Hız farkı yorum
            pf = t.get("pace_fark", 0) or 0
            if pf > 0.5:     pace_yorum = "Güçlü kapanış"
            elif pf > 0.2:   pace_yorum = "Hafif kapanış"
            elif pf < -0.5:  pace_yorum = "Erken yorulma"
            elif pf < -0.2:  pace_yorum = "Hafif düşüş"
            else:             pace_yorum = "Dengeli"

            # Hız aralığı (max-min)
            hiz_aralik = ""
            if t.get("max_hiz") and t.get("min_hiz"):
                hiz_aralik = f"{t['max_hiz']-t['min_hiz']:.2f}"

            row = {
                "At": at,
                "Tempo_Profili": t.get("tempo_profil", "—"),
                "Tempo_Skor": t.get("tempo_skor", ""),
                "Ref_Seviye": t.get("ref_seviye", "—"),
                "Ref_Fark": t.get("ref_fark", "—"),
                "Pace_Yorum": pace_yorum,
                "Ort_Hız(m/s)": t.get("ort_hiz", ""),
                "Max_Hız(m/s)": t.get("max_hiz", ""),
                "Min_Hız(m/s)": t.get("min_hiz", ""),
                "Hız_Aralık": hiz_aralik,
                "Erken_Pace": t.get("erken_pace", ""),
                "Geç_Pace": t.get("gec_pace", ""),
                "Pace_Fark": t.get("pace_fark", ""),
                "Son200(m/s)": t.get("son_200_hiz", ""),
                "Son400(m/s)": t.get("son_400_hiz", ""),
                "Mesafe": t.get("kosu_mesafe", ""),
                "Pist": t.get("kosu_pist", ""),
                "Sıra": t.get("sira", ""),
                "Derece": t.get("derece", ""),
                "Poz_Değişim": t.get("poz_degisim", "—"),
                "Veri": "📡" if t.get("kaynak") == "trakus" else "📊",
            }
            rows.append(row)

        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df = df.sort_values(
                "Tempo_Skor",
                key=lambda x: pd.to_numeric(x, errors="coerce").fillna(0),
                ascending=False).reset_index(drop=True)

        def tag_fn(row, idx):
            t = str(row.get("Tempo_Profili", ""))
            if "KAPANIŞ" in t:
                return "up"
            if "ERKEN" in t:
                return "dn"
            if "DENGELİ" in t:
                return "st"
            if idx == 0:
                return "g1"
            if idx == 1:
                return "g2"
            if idx == 2:
                return "g3"
            return "odd" if idx % 2 == 0 else "ev"

        self._fill_tree(self.tree_trakus, df, tag_fn=tag_fn)

        # Podium
        self._draw_trakus_podium(df.head(3).to_dict("records")
                                  if not df.empty else [])

        # Özet metin
        self._write_tempo_ozet(filtered)

        # Grafik
        self.after(100, self._draw_trakus_chart)

        n_trakus = sum(1 for v in filtered.values()
                       if v.get("kaynak") == "trakus")
        n_profil = sum(1 for v in filtered.values()
                       if v.get("kaynak") == "profil")
        self.trakus_info.set(
            f"{len(filtered)} at analiz edildi  |  "
            f"Trakus: {n_trakus}  |  Profil: {n_profil}")

    def _draw_trakus_podium(self, top3):
        for w in self.trakus_cards.winfo_children():
            w.destroy()
        if not top3:
            return

        tk.Label(self.trakus_cards, text="🏁  En İyi Tempo Performansı",
                 font=F_M, bg=BG, fg=TEXT).pack(side="left", padx=(0, 16))

        colors = [GOLD, SILVER, BRONZE]
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(top3):
            c = tk.Frame(self.trakus_cards, bg=CARD,
                         highlightthickness=2,
                         highlightbackground=colors[i],
                         padx=14, pady=8)
            c.pack(side="left", padx=(0, 10))
            tk.Label(c, text=f"{medals[i]} {row.get('At', '')}",
                     font=F_M, bg=CARD, fg=TEXT).pack()
            tk.Label(c, text=f"Tempo: {row.get('Tempo_Skor', '—')}",
                     font=("Segoe UI", 12, "bold"), bg=CARD,
                     fg=colors[i]).pack()
            det = (f"{row.get('Tempo_Profili', '')}  |  "
                   f"Ort: {row.get('Ort_Hız(m/s)', '')} m/s")
            tk.Label(c, text=det, font=F_XS, bg=CARD, fg=DIM
                     ).pack(pady=(2, 0))

    def _write_tempo_ozet(self, filtered):
        """Detaylı tempo raporu — koşu yorumu seviyesinde."""
        lines = []

        if not filtered:
            lines.append("Henüz tempo verisi yok. "
                         "📡 TJK Trakus Çek veya 📊 Profilden Tempo butonunu kullanın.")
        else:
            n = len(filtered)
            n_tr = sum(1 for v in filtered.values() if v.get("kaynak") == "trakus")
            n_pr = sum(1 for v in filtered.values() if v.get("kaynak") == "profil")
            lines.append(f"📋 TEMPO RAPORU  —  {n} at analiz edildi "
                         f"(Trakus: {n_tr}, Profil: {n_pr})")
            lines.append("─" * 60)

            # ── Kapanış güçlü atlar ──
            kapanis = [(at, t) for at, t in filtered.items()
                        if (t.get("pace_fark") or 0) > 0.2]
            kapanis.sort(key=lambda x: x[1].get("pace_fark", 0), reverse=True)
            if kapanis:
                lines.append("")
                lines.append("🟢 KAPANIŞ GÜÇLÜ (Son bölümlerde hız artışı):")
                for at, t in kapanis[:4]:
                    pf = t.get("pace_fark", 0)
                    s200 = t.get("son_200_hiz")
                    s200_txt = f", Son200: {s200:.2f} m/s" if s200 else ""
                    lines.append(
                        f"   • {at}: Erken {t.get('erken_pace',0):.2f} → "
                        f"Geç {t.get('gec_pace',0):.2f} m/s  "
                        f"(+{pf:.2f} fark{s200_txt})")
                lines.append("   → Uzun mesafe ve yüksek tempolu koşularda avantajlı. "
                             "Erken pace yavaşsa bu atlar finalde fark yaratır.")

            # ── Erken tempocular ──
            erken = [(at, t) for at, t in filtered.items()
                      if (t.get("pace_fark") or 0) < -0.2]
            erken.sort(key=lambda x: x[1].get("pace_fark", 0))
            if erken:
                lines.append("")
                lines.append("🔴 ERKEN TEMPO (Başta hızlı, sonda düşüş):")
                for at, t in erken[:4]:
                    pf = t.get("pace_fark", 0)
                    lines.append(
                        f"   • {at}: Erken {t.get('erken_pace',0):.2f} → "
                        f"Geç {t.get('gec_pace',0):.2f} m/s  "
                        f"({pf:.2f} fark)")
                lines.append("   → Sprint mesafelerinde (≤1200m) ve az rakipli "
                             "koşularda tercih edilir. Uzun mesafede risk.")

            # ── Dengeli ──
            dengeli = [(at, t) for at, t in filtered.items()
                        if abs(t.get("pace_fark") or 0) <= 0.2]
            if dengeli:
                lines.append("")
                ad = ", ".join(f"{a} ({t.get('ort_hiz',0):.2f})"
                               for a, t in dengeli[:4])
                lines.append(f"🟡 DENGELİ TEMPO: {ad}")
                lines.append("   → Baştan sona sabit hız — her mesafe ve pistte "
                             "tutarlı performans. Formda olduğunda güvenilir.")

            # ── Seksiyonel rekorlar ──
            lines.append("")
            lines.append("─" * 60)

            en_hizli = max(filtered.values(),
                           key=lambda t: t.get("max_hiz", 0), default=None)
            if en_hizli and en_hizli.get("max_hiz"):
                lines.append(
                    f"⚡ EN YÜKSEK SEKSİYONEL: {en_hizli['at']} → "
                    f"{en_hizli['max_hiz']:.2f} m/s  "
                    f"(patlama gücü yüksek)")

            en_dusuk_min = min(filtered.values(),
                                key=lambda t: t.get("min_hiz", 99), default=None)
            if en_dusuk_min and en_dusuk_min.get("min_hiz"):
                lines.append(
                    f"🐢 EN DÜŞÜK SEKSİYONEL: {en_dusuk_min['at']} → "
                    f"{en_dusuk_min['min_hiz']:.2f} m/s  "
                    f"(zayıf bölüm)")

            en_iyi = max(filtered.values(),
                         key=lambda t: t.get("tempo_skor", 0), default=None)
            if en_iyi:
                lines.append(
                    f"🏆 EN İYİ TEMPO SKORU: {en_iyi['at']} → "
                    f"{en_iyi['tempo_skor']}  "
                    f"({en_iyi.get('tempo_profil','')})")

            # Ort. hız sıralaması
            hiz_sirali = sorted(filtered.items(),
                                 key=lambda x: x[1].get("ort_hiz", 0),
                                 reverse=True)
            if len(hiz_sirali) >= 2:
                lines.append("")
                lines.append("📊 ORT HIZ SIRALAMASI:")
                for i, (at, t) in enumerate(hiz_sirali[:5], 1):
                    ref_txt = ""
                    if t.get("ref_seviye") and t["ref_seviye"] != "—":
                        ref_txt = f"  [{t['ref_seviye']}]"
                    lines.append(
                        f"   {i}. {at}: {t.get('ort_hiz',0):.2f} m/s  "
                        f"(max: {t.get('max_hiz',0):.2f}){ref_txt}")

            # ── Mesafe Referans Karşılaştırması ──
            ref_atlar = [(at, t) for at, t in filtered.items()
                         if t.get("ref_seviye") and t["ref_seviye"] != "—"]
            if ref_atlar:
                lines.append("")
                lines.append("─" * 60)
                # Mesafe bilgisi
                sample = ref_atlar[0][1]
                msf = sample.get("kosu_mesafe", 0)
                pist = sample.get("kosu_pist", "")
                ref_info = mesafe_tempo_bilgisi(msf, pist)
                if ref_info:
                    ref_iyi, ref_orta, ref_zayif = ref_info["ort_hiz_ms"]
                    lines.append(
                        f"📏 MESAFE REFERANSI: {msf}m {pist}")
                    lines.append(
                        f"   Referans hız → İyi: {ref_iyi:.2f}  |  "
                        f"Orta: {ref_orta:.2f}  |  Zayıf: {ref_zayif:.2f} m/s")
                    ref_d = ref_info["ref_derece"]
                    lines.append(
                        f"   Referans derece → İyi: {derece_formatla(ref_d[0])}  |  "
                        f"Orta: {derece_formatla(ref_d[1])}  |  "
                        f"Zayıf: {derece_formatla(ref_d[2])}")
                    lines.append(f"   Tempo tipi: {ref_info['tempo_tipi']}")
                    lines.append(f"   {ref_info['aciklama']}")
                    lines.append("")
                    lines.append("📊 REFERANSA GÖRE DEĞERLENDİRME:")
                    for at, t in sorted(ref_atlar,
                                        key=lambda x: x[1].get("ort_hiz", 0),
                                        reverse=True):
                        fark = t.get("ref_fark", 0) or 0
                        fark_txt = f"+{fark:.2f}" if fark > 0 else f"{fark:.2f}"
                        lines.append(
                            f"   {t['ref_seviye']} {at}: "
                            f"{t.get('ort_hiz',0):.2f} m/s  "
                            f"(fark: {fark_txt})")
                        # Seksiyonel karne
                        karne = t.get("ref_seks_karne", [])
                        if karne:
                            karne_txt = " | ".join(
                                f"{k['bolum']}:{k['durum']}"
                                for k in karne)
                            lines.append(f"      Seksiyonel: {karne_txt}")

            # ── GEÇİŞ DERECELERİ DETAYI ──
            lines.append("")
            lines.append("═" * 65)
            lines.append("🕐 GEÇİŞ DERECELERİ (Trakus Split Zamanları):")
            lines.append("")
            for at, t in sorted(filtered.items(),
                                key=lambda x: x[1].get("tempo_skor", 0),
                                reverse=True):
                seks = t.get("seksiyonlar", [])
                pozlar = t.get("pozisyonlar", {})
                if not seks:
                    continue
                kaynak = "📡 Trakus" if t.get("kaynak") == "trakus" else "📊 Profil"
                derece = t.get("derece", "—")
                sira = t.get("sira", "—")
                lines.append(
                    f"  {at} [{kaynak}]  Derece: {derece}  Sıra: {sira}")

                # Her seksiyonun split zamanı ve pozisyon
                gecis_parts = []
                for sek in seks:
                    b = sek["bitis"]
                    sure = sek["sure"]
                    hiz = sek["hiz_ms"]
                    poz = pozlar.get(b, "")
                    poz_txt = f" P:{poz}" if poz else ""
                    gecis_parts.append(
                        f"{b}m={sure:.2f}s({hiz:.1f}m/s{poz_txt})")
                lines.append(f"    {' → '.join(gecis_parts)}")

                # Koşu stili bilgisi (pozisyon değişimi)
                if pozlar:
                    poz_list = [(d, pozlar[d]) for d in sorted(pozlar.keys())]
                    if len(poz_list) >= 2:
                        ilk = poz_list[0]
                        son = poz_list[-1]
                        degisim = ilk[1] - son[1]
                        if degisim > 0:
                            stil_txt = f"↑ {degisim} sıra ilerledi ({ilk[1]}→{son[1]})"
                        elif degisim < 0:
                            stil_txt = f"↓ {abs(degisim)} sıra geriledi ({ilk[1]}→{son[1]})"
                        else:
                            stil_txt = f"= Sabit pozisyon ({ilk[1]})"
                        lines.append(f"    Pozisyon: {stil_txt}")
                lines.append("")

        self.txt_tempo.config(state="normal")
        self.txt_tempo.delete("1.0", "end")
        self.txt_tempo.insert("end", "\n".join(lines))
        self.txt_tempo.config(state="disabled")

    def _draw_trakus_chart(self):
        """Seksiyonel hız çoklu çizgi grafiği."""
        cv = self.cv_trakus
        cv.delete("all")
        W = cv.winfo_width() or 460
        H = cv.winfo_height() or 400
        if not self.tempo_an or W < 100:
            return

        # Koşu filtresi
        secim = self.trakus_kosu_var.get()
        if secim and secim not in ("Tümü",):
            m = re.search(r"(\d+)", secim)
            if m:
                kno = int(m.group(1))
                filtered = {k: v for k, v in self.tempo_an.items()
                            if v.get("kosu_no") == kno}
            else:
                filtered = self.tempo_an
        else:
            filtered = self.tempo_an

        # En iyi 8 at (tempo skoruna göre)
        items = sorted(filtered.items(),
                       key=lambda x: x[1].get("tempo_skor", 0),
                       reverse=True)[:8]
        if not items:
            cv.create_text(W // 2, H // 2,
                           text="Tempo verisi yok",
                           fill=DIM, font=F_M)
            return

        PL, PR, PT, PB = 55, 20, 40, 50

        # Tüm hız değerlerini topla
        all_hiz = []
        max_seks = 0
        for _, t in items:
            hiz = t.get("hizlar", [])
            all_hiz.extend(hiz)
            max_seks = max(max_seks, len(hiz))

        if not all_hiz or max_seks < 2:
            cv.create_text(W // 2, H // 2,
                           text="Yeterli seksiyonel veri yok",
                           fill=DIM, font=F_M)
            return

        mn = min(all_hiz) - 0.3
        mx = max(all_hiz) + 0.3
        rng = max(mx - mn, 0.1)
        xs = (W - PL - PR) / max(max_seks - 1, 1)

        cv.create_text(W // 2, 20,
                       text="Seksiyonel Hız Profili (m/s)",
                       fill=TEXT, font=F_S)

        # Grid
        for frac in [0, 0.25, 0.5, 0.75, 1.0]:
            val = mn + frac * rng
            y = PT + (1 - frac) * (H - PT - PB)
            cv.create_line(PL, y, W - PR, y, fill=BORDER, dash=(2, 5))
            cv.create_text(PL - 5, y, text=f"{val:.1f}",
                           fill=DIM, font=F_XS, anchor="e")

        # Her at için çizgi çiz
        for idx, (at, t) in enumerate(items):
            hiz = t.get("hizlar", [])
            if len(hiz) < 2:
                continue
            col = LINE_C[idx % len(LINE_C)]
            seks = t.get("seksiyonlar", [])

            pts = []
            for i, h in enumerate(hiz):
                x = PL + i * xs
                y = PT + (1 - (h - mn) / rng) * (H - PT - PB)
                pts.append((x, y))

            # Çizgi
            for i in range(len(pts) - 1):
                cv.create_line(pts[i][0], pts[i][1],
                               pts[i + 1][0], pts[i + 1][1],
                               fill=col, width=2)

            # Noktalar
            for x, y in pts:
                cv.create_oval(x - 3, y - 3, x + 3, y + 3,
                               fill=col, outline=BG)

            # İsim etiketi (son noktanın yanında)
            if pts:
                lx, ly = pts[-1]
                cv.create_text(lx + 5, ly,
                               text=at[:10],
                               fill=col, font=F_XS, anchor="w")

        # X ekseni etiketleri
        for i in range(max_seks):
            x = PL + i * xs
            lbl = f"{(i + 1) * 200}m"
            cv.create_text(x, H - PB + 14,
                           text=lbl, fill=DIM, font=F_XS)

        cv.create_line(PL, PT, PL, H - PB, fill=DIM)
        cv.create_line(PL, H - PB, W - PR, H - PB, fill=DIM)

        # Legend (sol alt)
        for i, (at, _) in enumerate(items[:4]):
            col = LINE_C[i % len(LINE_C)]
            ly = H - PB + 28 + i * 14
            cv.create_rectangle(PL, ly, PL + 10, ly + 10,
                                fill=col, outline="")
            cv.create_text(PL + 14, ly + 5,
                           text=at[:14], fill=col,
                           font=F_XS, anchor="w")

    def _update_trakus_tab(self):
        """Ana analiz akışı sonrası tempo analizini otomatik çalıştır."""
        if self.profiller:
            self.tempo_an = analiz_tempo(
                self.tjk_trakus or [], self.profiller)
            if self.tempo_an:
                self._on_trakus_done()

    # ── Tab: Genel Yarış Analizi ─────────────────────────

    def _build_genel_yaris_tab(self, parent):
        """Tüm veri kaynaklarını birleştiren kapsamlı yarış analizi sekmesi."""
        # Üst bilgi
        info_f = tk.Frame(parent, bg="#1A2030")
        info_f.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(info_f,
                 text=("🎯  GENEL YARIŞ ANALİZİ  —  "
                       "Galop + Stil + Performans + Tempo + Mesafe/Pist Uyumu "
                       "birleştirilerek tüm atlar için kapsamlı güç puanı hesaplanır."),
                 font=F_XS, bg="#1A2030", fg=DIM, wraplength=1400,
                 justify="left", padx=8, pady=4).pack(fill="x")

        # Podium
        self.gy_podium = tk.Frame(parent, bg=BG)
        self.gy_podium.pack(fill="x", padx=8, pady=(6, 4))

        # Mesafe referans kartı
        self.gy_ref_card = tk.Frame(parent, bg=CARD,
                                     highlightthickness=1,
                                     highlightbackground=BORDER)
        self.gy_ref_card.pack(fill="x", padx=8, pady=(0, 4))

        # Orta: ana tablo
        mid = tk.Frame(parent, bg=BG)
        mid.pack(fill="both", expand=True, padx=8)

        lp = tk.Frame(mid, bg=BG)
        lp.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(lp, text="Kapsamlı At Değerlendirmesi — Birleşik Güç Puanı",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 4))
        self.tree_gy = self._make_tree(lp)

        # Sağ: puan dağılım grafiği
        rp = tk.Frame(mid, bg=BG, width=420)
        rp.pack(side="left", fill="both")
        rp.pack_propagate(False)
        tk.Label(rp, text="Güç Puanı Dağılımı",
                 font=F_M, bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 4))
        self.cv_gy = tk.Canvas(rp, bg=PANEL,
                                highlightthickness=1,
                                highlightbackground=BORDER)
        self.cv_gy.pack(fill="both", expand=True)
        self.cv_gy.bind("<Configure>", lambda e: self._draw_gy_chart())

        # Alt: detaylı rapor
        bt = tk.Frame(parent, bg=BG)
        bt.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(bt, text="Yarış Raporu:", font=F_S, bg=BG, fg=GOLD
                 ).pack(side="left")
        self.txt_gy = tk.Text(bt, bg=PANEL, fg=TEXT, font=F_XS,
                               height=8, relief="flat",
                               highlightthickness=1,
                               highlightbackground=BORDER,
                               state="disabled", wrap="word")
        self.txt_gy.pack(fill="x", expand=True, padx=(6, 0))

    def _update_genel_yaris(self):
        """Genel yarış analizi sekmesini güncelle."""
        if not self.sel_kosu:
            return

        kosu = self.sel_kosu
        try:
            k_mesafe = int(kosu.get("mesafe", "0"))
        except (ValueError, TypeError):
            k_mesafe = 0
        k_pist = kosu.get("pist", "")

        sonuclar = analiz_genel_yaris(
            kosu.get("atlar", []),
            self.galop_an, self.stiller,
            self.performlar, self.tempo_an,
            k_mesafe, k_pist)

        self.genel_yaris_sonuc = sonuclar

        # Tablo
        rows = []
        for s in sonuclar:
            rows.append({
                "Sıra": s["tahmin_sira"],
                "No": s["no"],
                "At": s["at"],
                "Güç_Puanı": s["toplam_puan"],
                "Galop": s["galop_puan"],
                "Stil": s["stil_puan"],
                "Uyum": s["uyum_puan"],
                "Trend": s["trend_puan"],
                "Tempo": s["tempo_puan"],
                "Form": s["form"],
                "Koşu_Stili": s["stil"],
                "Mesafe_Uyum": s["mesafe_uyumu"],
                "Pist_Uyum": s["pist_uyumu"],
                "Momentum": s["momentum"],
                "Galop_Trend": s["galop_trend"],
                "Tutarlılık": s["tutarlilik"],
                "Yorum": s["yorum"],
            })

        df = pd.DataFrame(rows) if rows else pd.DataFrame()

        def tag_fn(row, idx):
            if idx == 0: return "g1"
            if idx == 1: return "g2"
            if idx == 2: return "g3"
            yorum = str(row.get("Yorum", ""))
            if "💪" in yorum and "⚠️" not in yorum:
                return "up"
            if "⚠️" in yorum and "💪" not in yorum:
                return "dn"
            return "odd" if idx % 2 == 0 else "ev"

        self._fill_tree(self.tree_gy, df, tag_fn=tag_fn)

        # Podium
        self._draw_gy_podium(sonuclar[:3] if sonuclar else [])

        # Mesafe referans kartı
        self._draw_gy_ref_card(k_mesafe, k_pist)

        # Rapor
        self._write_gy_rapor(sonuclar, k_mesafe, k_pist)

        # Grafik
        self.after(100, self._draw_gy_chart)

    def _draw_gy_podium(self, top3):
        for w in self.gy_podium.winfo_children():
            w.destroy()
        if not top3:
            return

        tk.Label(self.gy_podium, text="🎯  Tahmini En Güçlü Adaylar",
                 font=F_M, bg=BG, fg=TEXT).pack(side="left", padx=(0, 16))

        colors = [GOLD, SILVER, BRONZE]
        medals = ["🥇", "🥈", "🥉"]
        for i, s in enumerate(top3):
            c = tk.Frame(self.gy_podium, bg=CARD,
                         highlightthickness=2,
                         highlightbackground=colors[i],
                         padx=14, pady=8)
            c.pack(side="left", padx=(0, 10))
            tk.Label(c, text=f"{medals[i]} {s['at']}",
                     font=F_M, bg=CARD, fg=TEXT).pack()
            tk.Label(c, text=f"Güç: {s['toplam_puan']}",
                     font=("Segoe UI", 12, "bold"), bg=CARD,
                     fg=colors[i]).pack()
            det = (f"{s['form']}  |  {s['stil']}")
            tk.Label(c, text=det, font=F_XS, bg=CARD, fg=DIM).pack()
            det2 = (f"G:{s['galop_puan']} S:{s['stil_puan']} "
                    f"U:{s['uyum_puan']} T:{s['trend_puan']} "
                    f"Te:{s['tempo_puan']}")
            tk.Label(c, text=det2, font=F_XS, bg=CARD, fg=DIM
                     ).pack(pady=(2, 0))

    def _draw_gy_ref_card(self, mesafe, pist):
        """Mesafe referans bilgi kartını çiz."""
        for w in self.gy_ref_card.winfo_children():
            w.destroy()

        if not mesafe:
            tk.Label(self.gy_ref_card, text="Mesafe bilgisi mevcut değil",
                     font=F_XS, bg=CARD, fg=DIM, padx=8, pady=4).pack()
            return

        ref = mesafe_tempo_bilgisi(mesafe, pist)
        if not ref:
            tk.Label(self.gy_ref_card,
                     text=f"📏 {mesafe}m {pist} — Referans verisi bulunamadı",
                     font=F_XS, bg=CARD, fg=DIM, padx=8, pady=4).pack()
            return

        # Başlık
        tk.Label(self.gy_ref_card,
                 text=f"📏  MESAFE REFERANSI: {mesafe}m {pist}",
                 font=F_S, bg=CARD, fg=GOLD, padx=8, pady=(4, 2)
                 ).pack(anchor="w")

        # Detay satırı
        ref_d = ref["ref_derece"]
        ref_h = ref["ort_hiz_ms"]
        detail = (f"Derece → İyi: {derece_formatla(ref_d[0])} | "
                  f"Orta: {derece_formatla(ref_d[1])} | "
                  f"Zayıf: {derece_formatla(ref_d[2])}    "
                  f"Hız → İyi: {ref_h[0]:.2f} | "
                  f"Orta: {ref_h[1]:.2f} | "
                  f"Zayıf: {ref_h[2]:.2f} m/s    "
                  f"Tip: {ref['tempo_tipi']}")
        tk.Label(self.gy_ref_card, text=detail,
                 font=F_XS, bg=CARD, fg=TEXT, padx=8, pady=(0, 2)
                 ).pack(anchor="w")

        tk.Label(self.gy_ref_card, text=ref["aciklama"],
                 font=F_XS, bg=CARD, fg=DIM, padx=8, pady=(0, 4)
                 ).pack(anchor="w")

    def _write_gy_rapor(self, sonuclar, mesafe, pist):
        """Kapsamlı yarış raporu."""
        lines = []
        if not sonuclar:
            lines.append("Henüz analiz yapılmadı.")
        else:
            lines.append(f"🎯 KAPSAMLI YARIŞ ANALİZ RAPORU")
            lines.append(f"   Mesafe: {mesafe}m  |  Pist: {pist or '—'}  |  "
                         f"{len(sonuclar)} at değerlendirildi")
            lines.append("═" * 65)

            # Favori grubu
            lines.append("")
            lines.append("🏆 FAVORİ GRUBU (En yüksek güç puanı):")
            for s in sonuclar[:3]:
                lines.append(
                    f"   {s['tahmin_sira']}. {s['at']} — Güç: {s['toplam_puan']}")
                lines.append(
                    f"      [G:{s['galop_puan']} S:{s['stil_puan']} "
                    f"U:{s['uyum_puan']} T:{s['trend_puan']} "
                    f"Te:{s['tempo_puan']}]")
                lines.append(f"      {s['yorum']}")

            # Sürpriz adayları
            surpriz = [s for s in sonuclar[3:] if s["toplam_puan"] >= 35]
            if surpriz:
                lines.append("")
                lines.append("⚡ SÜRPRİZ ADAYLARI:")
                for s in surpriz[:3]:
                    lines.append(
                        f"   {s['tahmin_sira']}. {s['at']} — Güç: {s['toplam_puan']}")
                    lines.append(f"      {s['yorum']}")

            # Mesafe uyumlu atlar
            uyumlu = [s for s in sonuclar
                      if "ÇOK İYİ" in str(s.get("mesafe_uyumu", ""))]
            if uyumlu:
                lines.append("")
                lines.append("📏 MESAFE UYUMU YÜKSEK:")
                for s in uyumlu[:4]:
                    lines.append(f"   • {s['at']}: {s['mesafe_uyumu']}")

            # Form yükselen atlar
            formda = [s for s in sonuclar
                      if s.get("form") in ("🔥 ZİRVEDE", "🟢 FORMDA",
                                            "📈 YÜKSELİYOR")]
            if formda:
                lines.append("")
                lines.append("📈 FORMDA OLAN ATLAR:")
                for s in formda[:4]:
                    lines.append(
                        f"   • {s['at']}: {s['form']}  |  "
                        f"Momentum: {s['momentum']}  |  "
                        f"Galop: {s['galop_trend']}")

            # Riskli atlar
            riskli = [s for s in sonuclar
                      if "⚠️" in str(s.get("yorum", "")) and
                      "💪" not in str(s.get("yorum", ""))]
            if riskli:
                lines.append("")
                lines.append("⚠️ RİSKLİ ATLAR:")
                for s in riskli[:3]:
                    lines.append(f"   • {s['at']}: {s['yorum']}")

            # Tahmini sıralama
            lines.append("")
            lines.append("═" * 65)
            lines.append("📊 TAHMİNİ SIRALAMASI:")
            for s in sonuclar:
                bar_len = int(s["toplam_puan"] / 2)
                bar = "█" * bar_len + "░" * (50 - bar_len)
                lines.append(
                    f"   {s['tahmin_sira']:2d}. {s['at']:<20s} "
                    f"{bar} {s['toplam_puan']}")

        self.txt_gy.config(state="normal")
        self.txt_gy.delete("1.0", "end")
        self.txt_gy.insert("end", "\n".join(lines))
        self.txt_gy.config(state="disabled")

    def _draw_gy_chart(self):
        """Güç puanı bar grafiği."""
        cv = self.cv_gy
        cv.delete("all")
        W = cv.winfo_width() or 400
        H = cv.winfo_height() or 400
        if not hasattr(self, "genel_yaris_sonuc") or not self.genel_yaris_sonuc:
            cv.create_text(W // 2, H // 2, text="Analiz bekleniyor",
                           fill=DIM, font=F_M)
            return

        sonuclar = self.genel_yaris_sonuc[:10]
        n = len(sonuclar)
        if n == 0:
            return

        PL, PR, PT, PB = 110, 20, 30, 30
        bar_h = max(12, (H - PT - PB) / n - 4)
        max_puan = max(s["toplam_puan"] for s in sonuclar) or 1

        cv.create_text(W // 2, 14, text="Güç Puanı Karşılaştırması",
                       fill=TEXT, font=F_S)

        colors_list = [GOLD, SILVER, BRONZE, GREEN, BLUE,
                       TEAL, ORANGE, "#9B59B6", DIM, DIM]

        for i, s in enumerate(sonuclar):
            y = PT + i * (bar_h + 4)
            # At adı
            cv.create_text(PL - 5, y + bar_h / 2,
                           text=s["at"][:12], fill=TEXT,
                           font=F_XS, anchor="e")
            # Bar
            bw = max(5, (s["toplam_puan"] / max_puan) * (W - PL - PR))
            col = colors_list[i] if i < len(colors_list) else DIM
            cv.create_rectangle(PL, y, PL + bw, y + bar_h,
                                fill=col, outline="")
            # Puan
            cv.create_text(PL + bw + 5, y + bar_h / 2,
                           text=f"{s['toplam_puan']}",
                           fill=TEXT, font=F_XS, anchor="w")

            # Alt bileşenler (küçük renkli bloklar)
            bx = PL
            for val, c in [(s["galop_puan"], GREEN),
                           (s["stil_puan"], BLUE),
                           (s["uyum_puan"], TEAL),
                           (s["trend_puan"], ORANGE),
                           (s["tempo_puan"], "#9B59B6")]:
                seg_w = (val / max_puan) * (W - PL - PR)
                if seg_w > 1:
                    cv.create_rectangle(bx, y + bar_h - 3,
                                        bx + seg_w, y + bar_h,
                                        fill=c, outline="")
                    bx += seg_w

        # Legend
        ly = H - 18
        legend = [("Galop", GREEN), ("Stil", BLUE), ("Uyum", TEAL),
                  ("Trend", ORANGE), ("Tempo", "#9B59B6")]
        lx = PL
        for txt, col in legend:
            cv.create_rectangle(lx, ly, lx + 10, ly + 10,
                                fill=col, outline="")
            cv.create_text(lx + 13, ly + 5, text=txt,
                           fill=DIM, font=F_XS, anchor="w")
            lx += 60

    # ── Export ───────────────────────────────────────────

    def export_excel(self):
        if not self.sel_kosu:
            messagebox.showwarning("Uyarı","Veri yok."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel","*.xlsx")],
            initialfile=f"analiz_{self.bulten['sehir']}_{self.bulten['tarih'].replace('.','')}.xlsx")
        if not path: return

        atlar = self.sel_kosu.get("atlar",[])
        rows  = []
        for at in atlar:
            adi = at.get("at","")
            g   = self.galop_an.get(adi,{})
            s   = self.stiller.get(adi,{})
            p   = self.performlar.get(adi,{})
            rows.append({
                "No":at.get("no",""),"At":adi,"AGF":at.get("agf",""),
                "Hnd":at.get("hnd",""),"Kilo":at.get("kilo",""),
                "Jokey":at.get("jokey",""),"Taki":at.get("taki",""),
                "Son10":at.get("son10_str",""),
                "En_Iyi_400":g.get("en_iyi_400",""),"Ort_400":g.get("ort_400",""),
                "Son_Galop_Gun":g.get("gun_fark",""),
                "Kosu_Stili":s.get("stil",""),"Ort_Sira":s.get("ort_sira",""),
                "Ilk3_%":s.get("ilk3_pct",""),"Son5":s.get("son5",""),
                "Pist_Pref":s.get("pist_pref",""),
                "Trend":p.get("trend",""),"Trend_Skor":p.get("trend_skor",""),
            })

        with pd.ExcelWriter(path, engine="openpyxl") as w:
            pd.DataFrame(rows).to_excel(w, index=False, sheet_name="Analiz")
            if self.galoplar:
                pd.DataFrame(self.galoplar).to_excel(w, index=False, sheet_name="Galoplar")
            if self.tempo_an:
                tempo_rows = []
                for at, t in self.tempo_an.items():
                    tempo_rows.append({
                        "At": at, "Tempo_Profil": t.get("tempo_profil",""),
                        "Tempo_Skor": t.get("tempo_skor",""),
                        "Ort_Hiz": t.get("ort_hiz",""),
                        "Max_Hiz": t.get("max_hiz",""),
                        "Erken_Pace": t.get("erken_pace",""),
                        "Gec_Pace": t.get("gec_pace",""),
                        "Pace_Fark": t.get("pace_fark",""),
                        "Son200_Hiz": t.get("son_200_hiz",""),
                        "Poz_Degisim": t.get("poz_degisim",""),
                        "Kaynak": t.get("kaynak",""),
                    })
                pd.DataFrame(tempo_rows).to_excel(
                    w, index=False, sheet_name="Tempo")
            for sheet in w.sheets.values():
                for col in sheet.columns:
                    mx = max(len(str(c.value or "")) for c in col)
                    sheet.column_dimensions[col[0].column_letter].width = min(mx+2,35)
        messagebox.showinfo("✓ Kaydedildi", path)

    def export_csv(self):
        if not self.galoplar:
            messagebox.showwarning("Uyarı","Galop verisi yok."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="galoplar.csv")
        if not path: return
        pd.DataFrame(self.galoplar).to_csv(path, index=False, encoding="utf-8-sig")
        messagebox.showinfo("✓ Kaydedildi", path)


if __name__ == "__main__":
    App().mainloop()
