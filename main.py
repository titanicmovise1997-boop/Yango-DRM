import json, re, base64, requests
from flask import Flask, render_template, request
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

app = Flask(__name__)

# تحميل جهاز الـ L3
try:
    device = Device.load("./device.wvd")
except Exception as e:
    print(f"❌ خطأ في تحميل ملف الجهاز: {e}")

def extract_yango_keys(pssh_b64, curl_content):
    if not pssh_b64 or not curl_content:
        return {"status": "error", "msg": "بيانات ناقصة: تأكد من وضع الـ PSSH ورفع الملف."}

    try:
        cdm = Cdm.from_device(device)
        session_id = cdm.open()
        challenge = cdm.get_license_challenge(session_id, PSSH(pssh_b64))
        
        # استخراج الرابط بالكامل
        url_match = re.search(r"curl\s+'(https://.*?)'", curl_content)
        license_url = url_match.group(1) if url_match else "https://widevine-proxy.movies.funtechservices.com/proxy"

        # استخراج البيانات الديناميكية لمنع التعارض (حل مشكلة 418)
        puid = re.search(r'"puid":(\d+)', curl_content)
        wSid = re.search(r'"watchSessionId":"(.*?)"', curl_content)
        cId = re.search(r'"contentId":"(.*?)"', curl_content)
        cTypeId = re.search(r'"contentTypeId":(\d+)', curl_content) 
        sig = re.search(r'"signature":"(.*?)"', curl_content)
        exp = re.search(r'"expirationTimestamp":(\d+)', curl_content)

        payload = {
            "puid": int(puid.group(1)) if puid else 0,
            "watchSessionId": wSid.group(1) if wSid else "",
            "contentId": cId.group(1) if cId else "",
            "contentTypeId": int(cTypeId.group(1)) if cTypeId else 20,
            "serviceName": "yango-movies-web",
            "productId": 2,
            "monetizationModel": "SVOD",
            "expirationTimestamp": int(exp.group(1)) if exp else 0,
            "verificationRequired": True,
            "signature": sig.group(1) if sig else "",
            "version": "V4",
            "rawLicenseRequestBase64": base64.b64encode(challenge).decode('utf-8')
        }

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Origin': 'https://play.yango.com',
            'Referer': 'https://play.yango.com/'
        }

        response = requests.post(license_url, json=payload, headers=headers)

        if response.status_code == 200:
            try:
                resp_json = response.json()
                license_data = resp_json.get('rawLicenseResponseBase64', response.content)
            except:
                license_data = response.content
            
            cdm.parse_license(session_id, license_data)
            keys_list = []
            for key in cdm.get_keys(session_id):
                if key.type == 'CONTENT':
                    k_id = key.kid.hex() if callable(getattr(key.kid, 'hex', None)) else key.kid.hex
                    k_val = key.key.hex() if callable(getattr(key.key, 'hex', None)) else key.key.hex
                    keys_list.append(f"{k_id}:{k_val}")
            
            cdm.close(session_id)
            return {"status": "success", "extracted_keys": keys_list, "contentId": payload["contentId"]}

        return {"status": "error", "msg": f"❌ فشل يانغو ({response.status_code})"}

    except Exception as e:
        return {"status": "error", "msg": f"❌ خطأ تقني: {str(e)}"}

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        pssh = request.form.get('pssh')
        file = request.files.get('curl_file')
        if pssh and file:
            try:
                curl_content = file.read().decode('utf-8', errors='ignore')
                result = extract_yango_keys(pssh, curl_content)
            except Exception as e:
                result = {"status": "error", "msg": f"❌ فشل قراءة الملف: {str(e)}"}
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)