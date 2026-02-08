import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import base64
import json

# استيراد مكتبات Widevine (تأكد من وجود ملفات الـ WVD في نفس المجلد)
# بدلاً من المسار القديم اللي كان فيه .L3.
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

app = Flask(__name__)
app.secret_key = 'bio_elite_secure_2026_key' # مفتاح تشفير الجلسة

# --- إعدادات تسجيل الدخول ---
ADMIN_USER = "ismail"
ADMIN_PASS = "mynamefrank@2026"

# --- إعدادات الـ CDM (ملف الـ Device الخاص بك) ---
# تأكد من وضع ملف الـ .wvd في نفس مجلد السكريبت
DEVICE_PATH = "device.wvd" 

def get_keys(pssh_base64, license_url, cert_data=None):
    """دالة استخراج المفاتيح من سيرفر الترخيص"""
    try:
        device = Device.load(DEVICE_PATH)
        cdm = Cdm.from_device(device)
        session_id = cdm.open().decode()
        
        # تجهيز الـ Challenge
        challenge = cdm.get_license_challenge(session_id, PSSH(pssh_base64))
        
        # إرسال الطلب لسيرفر يانجو بلاي
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        # ملاحظة: هنا يجب تمرير الـ Headers المستخرجة من ملف الـ cURL الذي يرفعه المستخدم
        # للتبسيط، هذا هو المنطق الأساسي:
        response = requests.post(license_url, data=challenge, headers=header)
        
        if response.status_code != 200:
            return {"status": "error", "msg": f"License Server Error: {response.status_code}"}
            
        cdm.parse_license(session_id, response.content)
        keys = []
        for key in cdm.get_keys(session_id):
            if key.type == 'CONTENT':
                keys.append(f"{key.kid.hex}:{key.key.hex()}")
        
        cdm.close(session_id)
        return {"status": "success", "keys": keys}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

# --- المسارات (Routes) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = "⚠️ بيانات الدخول غير صحيحة!"
            
    return render_template('login.html', error=error)

@app.route('/', methods=['GET', 'POST'])
def index():
    # حماية المسار: التأكد من تسجيل الدخول
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    result = None
    if request.method == 'POST':
        pssh = request.form.get('pssh')
        # هنا بنفترض إنك بتعالج ملف الـ cURL المرفوع لاستخراج الـ License URL والـ Headers
        # سأضع لك هيكل النتيجة للتجربة:
        
        # افتراض نجاح العملية (كود تجريبي):
        # في الكود الفعلي، ستقوم باستدعاء get_keys هنا
        result = {
            "status": "success",
            "extracted_keys": ["8a3f4b2c1d9e0f8a7b6c5d4e3f2a1b0c:f1e2d3c4b5a697887766554433221100"],
            "contentId": "Yango_Movie_1080p"
        }
        
    return render_template('index.html', result=result)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # تأكد من وجود المجلدات اللازمة
    if not os.path.exists('templates'):
        os.makedirs('templates')
    if not os.path.exists('static'):
        os.makedirs('static')
        
    print("🚀 Bio-Elite Platform is starting on http://127.0.0.1:5000")
    app.run(debug=True)