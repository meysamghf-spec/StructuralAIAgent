# راهنمای استقرار در ایران (StructuralAIAgent)

هدف: اجرای backend (FastAPI) + frontend (Next.js) + PostgreSQL + فضای فایل، روی سرویسی که از ایران در دسترس است، تحریم نیست و با ریال پرداخت می‌شود — **با کمترین هزینهٔ ماهانه**.

## ۱. انتخاب

| گزینه | چه می‌خرید | هزینهٔ تقریبی ماهانه |
|---|---|---|
| **اصلی (ارزان‌ترین): VPS ایرانی + docker-compose** (مثلاً پارس‌پک irVPS2: ۱ هسته / ۲ گیگ رم / ۴۰ گیگ SSD) | یک سرور؛ همه‌چیز (DB، فایل، HTTPS) روی همان | حدود ۰٫۸ تا ۱٫۵ میلیون تومان (قیمت دقیق را در پنل ببینید) |
| **پشتیبان: لیارا (PaaS)** | backend (مریخ) + frontend (زمین) + PostgreSQL (زمین) + دیسک | حدود ۲٫۸ میلیون تومان به بالا |

حداقل منابع: ۲ گیگ رم (۱ گیگ برای build کافی نیست). اگر build کند بود، پلن ۲ هسته‌ای (irVPS3) بگیرید.

## ۲. دامنه (.ir از nic.ir)
1. در https://www.nic.ir ثبت‌نام و احراز هویت (verify.nic.ir) کنید.
2. دامنه را ثبت کنید (یک‌ساله ≈ ۹۲ هزار تومان طبق تعرفهٔ ۱۴۰۵).
3. DNS: یک رکورد **A** برای `app.your-domain.ir` به IP سرور. (اگر از ابر آروان برای DNS استفاده می‌کنید، پروکسی/ابر نارنجی را برای شروع خاموش بگذارید تا Caddy بتواند گواهی بگیرد.)

## ۳. استقرار روی VPS (گزینهٔ اصلی)
```bash
# روی سرور Ubuntu 22.04/24.04
curl -fsSL https://get.docker.com | sh        # اگر در دسترس نبود: مخزن docker از mirror آروان/رانفلر
sudo mkdir -p /etc/docker && echo '{"registry-mirrors":["https://docker.arvancloud.ir"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
# swap برای build روی رم ۲ گیگ
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile

sudo mkdir -p /opt/sazeh && cd /opt/sazeh
# کد را بیاورید (git clone یا آپلود zip و unzip)
cp .env.production.example .env.production
nano .env.production    # DOMAIN، CORS_ORIGINS، رمزها را پر کنید
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```
رمزها: `openssl rand -hex 48` برای AUTH_JWT_SECRET و `openssl rand -hex 24` برای POSTGRES_PASSWORD.

### mirrorها (اگر دانلود بسته‌ها خطا داد)
در `.env.production`:
```
REGISTRY=docker.arvancloud.ir/
PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
NPM_REGISTRY=https://package-mirror.liara.ir/repository/npm/
```
(جایگزین: mirrorهای Runflare.)

### SSL
کاملاً خودکار است: Caddy با Let's Encrypt گواهی می‌گیرد و تمدید می‌کند. شرط: پورت‌های ۸۰ و ۴۴۳ باز و رکورد A درست باشد. بررسی: `https://app.your-domain.ir/health`.

### حالت راه‌اندازی رایگان
درگاه رمزارزی (BTCPay) و CoinGecko در ایران کاربردی نیستند؛ پس `PAYMENTS_ENABLED=false` همهٔ امکانات را بدون محدودیت پلن باز می‌کند. موتور تحلیل/طراحی قاب سه‌بعدی قطعی است و به LLM نیاز ندارد (`AI_ALLOW_DETERMINISTIC_IN_PRODUCTION=true`). بقیهٔ کنترل‌های امنیتی (ورود اجباری، دسترسی پروژه، JWT، CORS) فعال می‌مانند.

## ۴. پشتیبان‌گیری
```bash
chmod +x deploy/backup.sh && ./deploy/backup.sh
crontab -e   # 30 3 * * * cd /opt/sazeh && ./deploy/backup.sh >> backups/cron.log 2>&1
```
پوشهٔ `backups/` را هر هفته به جای دیگری (فضای بکاپ رایگان پارس‌پک یا object storage) کپی کنید.
بازیابی DB:
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db pg_restore -U app -d structuralaiaagent --clean < backups/db-XXXX.dump
```

## ۵. به‌روزرسانی
```bash
cd /opt/sazeh && git pull     # یا zip جدید
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker image prune -f
```
migrationها خودکار و فقط یک‌بار اجرا می‌شوند (جدول `applied_migration_files`). قبل از هر به‌روزرسانی یک بکاپ بگیرید.

## ۶. گزینهٔ پشتیبان: لیارا
1. در liara.ir: دو برنامهٔ Docker (`sazeh-backend` پلن مریخ، `sazeh-frontend` پلن زمین)، یک PostgreSQL (زمین) و یک دیسک `files` بسازید.
2. `npm i -g @liara/cli && liara login`
3. backend: `cp liara.backend.json liara.json && liara deploy` ؛ متغیرهای `.env.production.example` را در بخش «تنظیمات» برنامه وارد کنید و `DATABASE_URL` را از صفحهٔ دیتابیس بگذارید.
4. frontend: در `liara.frontend.json` آدرس API را اصلاح کنید، سپس `cp liara.frontend.json liara.json && liara deploy`.
5. دامنه‌ها (`app.` و `api.`) را در بخش دامنه اضافه کنید؛ SSL رایگان خودکار است. `CORS_ORIGINS` را برابر آدرس frontend بگذارید. `TRUSTED_PROXY_HOSTS` را مطابق مستندات لیارا تنظیم کنید یا `TRUST_PROXY_HEADERS=false`.
6. بکاپ DB در لیارا خودکار است.
