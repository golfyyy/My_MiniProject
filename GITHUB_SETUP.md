# อัปโหลดไป GitHub: golfyyy / My_MiniProject

## ขั้นที่ 1 — สร้าง Repo บน GitHub (ทำครั้งเดียว)

1. เปิด https://github.com/new
2. **Repository name:** `My_MiniProject`
3. เลือก **Private** (แนะนำ)
4. **อย่า** ติ๊ก Add a README file / .gitignore / license
5. กด **Create repository**

## ขั้นที่ 2 — รันสคริปต์ในเครื่อง

เปิด **PowerShell**:

```powershell
cd C:\Users\USER\GoldAI_Project
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\push_to_github.ps1
```

สคริปต์จะ:
- `git init` (ถ้ายังไม่มี)
- ตรวจว่าไม่ commit `.env` หรือ `config/settings.json`
- commit ครั้งแรก
- push ไป `https://github.com/golfyyy/My_MiniProject.git`

## Login ตอน push

- **Username:** `golfyyy`
- **Password:** ใช้ **Personal Access Token** (ไม่ใช่รหัสผ่าน GitHub ปกติ)

สร้าง Token: GitHub → Settings → Developer settings → Personal access tokens → Generate (เลือก scope `repo`)

## อัปเดตครั้งถัดไป

```powershell
cd C:\Users\USER\GoldAI_Project
git add .
git commit -m "คำอธิบายการแก้ไข"
git push
```

## ไฟล์ที่ไม่ขึ้น GitHub (ปลอดภัย)

ดูใน `.gitignore`: `.env`, `config/settings.json`, `*.db`, logs, น้ำหนักที่เรียนรู้แล้ว
