# -*- coding: utf-8 -*-

import os
import logging
import random
import io
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMember,
    ChatMemberUpdated,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ChatMemberHandler,
    ConversationHandler,
)
from telegram.constants import ParseMode
import psycopg2
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import time

# --- پیکربندی اصلی ---
OWNER_IDS = [7662192190, 6041119040] # آیدی‌های عددی ادمین‌های اصلی ربات
SUPPORT_USERNAME = "OLDKASEB" # یوزرنیم پشتیبانی بدون @
FORCED_JOIN_CHANNEL = "@RHINOSOUL_TM" # کانال عضویت اجباری با @
GROUP_INSTALL_LIMIT = 50 # حداکثر تعداد گروه‌هایی که ربات می‌تواند در آن‌ها نصب شود
INITIAL_LIVES = 12 # تعداد جان اولیه در بازی حدس کلمه

# --- تعریف حالت‌های مکالمه ---
# برای بازی قارچ
ASKING_GOD_USERNAME, CONFIRMING_GOD = range(2)
# برای بازی حدس عدد
SELECTING_RANGE, GUESSING = range(2, 4)
# برای اعتراف سفارشی
ENTERING_ETERAF_TEXT = range(4, 5)

# --- لیست کلمات و جملات (بدون تغییر) ---
WORD_LIST = [
    "فضاپیما", "کهکشان", "الگوریتم", "کتابخانه", "دانشگاه", "کامپیوتر", "اینترنت", "برنامه", "نویسی", "هوش", "مصنوعی", "یادگیری", "ماشین", "شبکه", "عصبی", "داده", "کاوی", "پایتون", "جاوا", "اسکریپت", 
    "فناوری", "اطلاعات", "امنیت", "سایبری", "حمله", "ویروس", "بدافزار", "آنتی", "ویروس", "دیوار", "آتش", "رمزنگاری", "پروتکل", "دامنه", "میزبانی", "وب", "سرور", "کلاینت", "پایگاه", "داده", 
    "رابط", "کاربری", "تجربه", "کاربری", "طراحی", "گرافیک", "انیمیشن", "سه", "بعدی", "واقعیت", "مجازی", "افزوده", "بلاکچین", "ارز", "دیجیتال", "بیتکوین", "اتریوم", "قرارداد", "هوشمند", "متاورس", 
    "اشیاء", "رباتیک", "خودرو", "خودران", "پهپاد", "سنسور", "پردازش", "تصویر", "سیگنال", "مخابرات", "ماهواره", "فرکانس", "موج", "الکترومغناطیس", "فیزیک", "کوانتوم", "نسبیت", "انیشتین", "نیوتن", 
    "گرانش", "سیاهچاله", "ستاره", "نوترونی", "انفجار", "بزرگ", "کیهان", "شناسی", "اختر", "فیزیک", "شیمی", "آلی", "معدنی", "تجزیه", "بیوشیمی", "ژنتیک", "سلول", "بافت", "ارگان", "متابولیسم", 
    "فتوسنتز", "تنفس", "سلولی", "زیست", "شناسی", "میکروبیولوژی", "باکتری", "قارچ", "پزشکی", "داروسازی", "جراحی", "قلب", "مغز", "اعصاب", "روانشناسی", "جامعه", "شناسی", "اقتصاد", "بازار", 
    "سرمایه", "بورس", "سهام", "تورم", "رکود", "رشد", "اقتصادی", "تولید", "ناخالص", "داخلی", "صادرات", "واردات", "تجارت", "بین", "الملل", "سیاست", "دموکراسی", "دیکتاتوری", "جمهوری", "پادشاهی", 
    "انتخابات", "پارلمان", "دولت", "قوه", "قضائیه", "تاریخ", "باستان", "معاصر", "جنگ", "جهانی", "صلیبی", "رنسانس", "اصلاحات", "دینی", "انقلاب", "صنعتی", "فلسفه", "منطق", "اخلاق", "زیبایی", 
    "شناسی", "افلاطون", "ارسطو", "سقراط", "دکارت", "کانت", "نیچه", "ادبیات", "شعر", "رمان", "داستان", "کوتاه", "نمایشنامه", "حافظ", "سعدی", "فردوسی", "مولانا", "خیام", "شکسپیر", "تولستوی", 
    "داستایوفسکی", "هنر", "نقاشی", "مجسمه", "سازی", "معماری", "موسیقی", "سینما", "تئاتر", "عکاسی", "خورشید", "سیاره", "مریخ", "زمین", "مشتری", "اورانوس", "نپتون", "زهره", "عطارد", "ستاره", 
    "دنباله", "دار", "شهاب", "سنگ", "صورت", "فلکی", "تلسکوپ", "رصدخانه", "فیزیکدان", "شیمیدان", "زیست", "شناس", "ریاضیات", "هندسه", "جبر", "مثلثات", "حسابان", "دیفرانسیل", "انتگرال", "آمار", 
    "احتمال", "ماتریس", "بردار", "اقلیدس", "فیثاغورس", "خوارزمی", "ابن", "سینا", "رازی", "بیرونی", "عنصر", "جدول", "تناوبی", "اتم", "مولکول", "یون", "ایزوتوپ", "واکنش", "شیمیایی", "کاتالیزور", 
    "آنزیم", "پروتئین", "کربوهیدرات", "لیپید", "ویتامین", "ماده", "معدنی", "دی", "ان", "ای", "ژن", "کروموزوم", "جهش", "تکامل", "داروین", "لامارک", "محیط", "زیست", "اکوسیستم", "آلودگی", "گرمایش", 
    "جهانی", "بازیافت", "انرژی", "تجدیدپذیر", "خورشیدی", "بادی", "برق", "آبی", "زمین", "گرمایی", "جنگل", "بیابان", "اقیانوس", "دریا", "رودخانه", "دریاچه", "کوهستان", "آتشفشان", "زلزله", "سونامی", 
    "طوفان", "گردباد", "خشکسالی", "سیل", "قاره", "آسیا", "اروپا", "آفریقا", "آمریکا", "اقیانوسیه", "قطب", "شمال", "جنوب", "استوا", "نصف", "النهار", "مدار", "جغرافیا", "نقشه", "قطب", "نما", 
    "تمدن", "مصر", "یونان", "روم", "ایران", "چین", "هند", "بین", "النهرین", "سومر", "بابل", "آشور", "هخامنشیان", "اشکانیان", "ساسانیان", "اسلام", "مغول", "صفویه", "قاجار", "پهلوی", "جمهوری", 
    "اسلامی", "اسطوره", "افسانه", "حماسه", "رستم", "سهراب", "اسفندیار", "سیمرغ", "ضحاک", "کاوه", "آهنگر", "گیلگمش", "هرکول", "زئوس", "آپولو", "پوزیدون", "هرمس", "آفرودیت", "جشنواره", "کارناوال", 
    "فستیوال", "المپیک", "جام", "جهانی", "فوتبال", "بسکتبال", "والیبال", "کشتی", "وزنه", "برداری", "دو", "میدانی", "شنا", "ژیمناستیک", "ورزشگاه", "استادیوم", "قهرمان", "مدال", "طلا", "نقره", "برنز", 
    "رکورد", "پایتخت", "تهران", "پاریس", "لندن", "رم", "نیویورک", "توکیو", "پکن", "مسکو", "برلین", "مادرید", "قاهره", "استانبول", "سیدنی", "تورنتو", "دبی", "ریاض", "دوحه", "پادشاه", "ملکه", 
    "شاهزاده", "رئیس", "جمهور", "نخست", "وزیر", "سفیر", "دیپلمات", "دیپلماسی", "مذاکره", "قرارداد", "پیمان", "صلح", "آتش", "بس", "ارتش", "سپاه", "نیروی", "هوایی", "دریایی", "زمینی", "سرباز", 
    "افسر", "ژنرال", "فرمانده", "جنگ", "نبرد", "عملیات", "استراتژی", "تاکتیک", "سلاح", "موشک", "تانک", "هواپیما", "ناو", "زیردریایی", "جاسوسی", "اطلاعات", "پروپاگاندا", "سانسور", "آزادی", 
    "بیان", "حقوق", "بشر", "شهروند", "مهاجرت", "پناهنده", "مرز", "گذرنامه", "ویزا", "جهانگردی", "توریسم", "هتل", "رستوران", "فرودگاه", "بندر", "ایستگاه", "قطار", "اتوبوس", "تاکسی", "مترو", 
    "بزرگراه", "خیابان", "کوچه", "میدان", "چهارراه", "چراغ", "راهنمایی", "پل", "تونل", "ساختمان", "آسمان", "خراش", "برج", "آپارتمان", "ویلا", "کلبه", "قصر", "قلعه", "موزه", "گالری", "کتابفروشی", 
    "کنسرت", "اپرا", "باله", "نمایشگاه", "باغ", "وحش", "پارک", "جنگلی", "ساحل", "پلاژ", "اسکله", "قایق", "کشتی", "لنج", "جت", "اسکی", "غواصی", "موج", "سواری", "اسکی", "اسنوبرد", "کوهنوردی", 
    "صخره", "نوردی", "طبیعت", "گردی", "فیلمبرداری", "خوشنویسی", "سفالگری", "جواهرسازی", "خیاطی", "گلدوزی", "بافتنی", "آشپزی", "شیرینی", "پزی", "نانوایی", "قنادی", "کافه", "قهوه", "چای", "نوشیدنی", 
    "صبحانه", "ناهار", "شام", "دسر", "پیش", "غذا", "سالاد", "سوپ", "کباب", "پیتزا", "ساندویچ", "پاستا", "برنج", "خورش", "سبزیجات", "میوه", "خشکبار", "آجیل", "ادویه", "زعفران", "هل", "دارچین", 
    "زنجبیل", "فلفل", "نمک", "شکر", "عسل", "مربا", "شکلات", "بستنی", "کیک", "شیرینی", "بیمارستان", "درمانگاه", "مطب", "داروخانه", "پزشک", "پرستار", "جراح", "متخصص", "دندانپزشک", "چشم", "پزشک", 
    "داروساز", "آمبولانس", "اورژانس", "بیماری", "سلامتی", "درمان", "واکسن", "آنتی", "بیوتیک", "قرص", "شربت", "آمپول", "سرم", "آزمایشگاه", "رادیولوژی", "سونوگرافی", "سی", "تی", "اسکن", "ام", "آر", "آی", 
    "مدرسه", "دبیرستان", "هنرستان", "کالج", "آموزشگاه", "زبان", "معلم", "دبیر", "استاد", "دانش", "آموز", "دانشجو", "کلاس", "درس", "امتحان", "کنکور", "پایان", "نامه", "رساله", "دکترا", "کارشناسی", 
    "ارشد", "لیسانس", "دیپلم", "تحصیلات", "پژوهش", "مقاله", "علمی", "مجله", "کنفرانس", "سمینار", "کارگاه", "آموزشی", "شرکت", "کارخانه", "اداره", "سازمان", "موسسه", "بنیاد", "انجمن", "اتحادیه", 
    "سندیکا", "مدیر", "کارمند", "کارگر", "کارشناس", "مشاور", "تحلیلگر", "حسابدار", "وکیل", "قاضی", "دادگاه", "دادسرا", "زندان", "پلیس", "آگاهی", "جرم", "جنایت", "متهم", "شاکی", "شاهد", "مجازات", 
    "جریمه", "حبس", "اعدام", "خانواده", "پدر", "مادر", "فرزند", "برادر", "خواهر", "پدربزرگ", "مادربزرگ", "نوه", "عمو", "عمه", "دایی", "خاله", "ازدواج", "طلاق", "تولد", "مرگ", "عروسی", "عزاداری", 
    "جشن", "مهمانی", "دوست", "رفیق", "همکار", "همسایه", "عشق", "نفرت", "شادی", "غم", "خشم", "ترس", "امید", "ناامیدی", "اعتماد", "خیانت", "شجاعت", "بزدلی", "صداقت", "دروغ", "عدالت", "بی", 
    "عدالتی", "آرامش", "استرس", "موفقیت", "شکست", "ثروت", "فقر", "قدرت", "ضعف", "زیبایی", "زشتی", "جوانی", "پیری", "کودکی", "نوجوانی", "بزرگسالی", "خاطره", "رویا", "آرزو", "هدف", "برنامه", "ریزی", 
    "آینده", "گذشته", "حال", "زمان", "ساعت", "دقیقه", "ثانیه", "روز", "هفته", "ماه", "سال", "قرن", "دهه", "تقویم", "فصل", "بهار", "تابستان", "پاییز", "زمستان", "آب", "هوا", "آفتابی", "ابری", "بارانی", 
    "برفی", "باد", "مه", "رعد", "برق", "رنگین", "کمان", "رنگ", "قرمز", "آبی", "زرد", "سبز", "نارنجی", "بنفش", "صورتی", "قهوه", "ای", "سیاه", "سفید", "خاکستری", "طلا", "نقره", "مس", "آهن", "آلومینیوم", 
    "فولاد", "پلاستیک", "شیشه", "چوب", "سنگ", "پارچه", "لباس", "پوشاک", "کفش", "کیف", "کلاه", "عینک", "جواهرات", "عطر", "ادکلن", "لوازم", "آرایش", "بهداشتی", "شامپو", "صابون", "خمیر", "دندان", 
    "مسواک", "حوله", "خانه", "آشپزخانه", "اتاق", "خواب", "پذیرایی", "حمام", "دستشویی", "مبلمان", "فرش", "پرده", "لوستر", "تلویزیون", "یخچال", "اجاق", "گاز", "ماشین", "لباسشویی", "ظرفشویی", 
    "مایکروویو", "جاروبرقی", "تلفن", "همراه", "تبلت", "لپتاپ", "دوربین", "بلندگو", "هدفون", "کتاب", "دفتر", "خودکار", "مداد", "پاک", "کن", "تراش", "خط", "کش", "پرگار", "کاغذ", "مقوا", "چسب", "قیچی", "منگنه", "روزنامه"
]
TYPING_SENTENCES = [
    "در یک دهکده کوچک مردی زندگی میکرد که به شجاعت و دانایی مشهور بود", "فناوری بلاکچین پتانسیل ایجاد تحول در صنایع مختلف را دارد", 
    "یادگیری یک زبان برنامه نویسی جدید میتواند درهای جدیدی به روی شما باز کند", "کتاب خواندن بهترین راه برای سفر به دنیاهای دیگر بدون ترک کردن خانه است", 
    "شب های پرستاره کویر منظره ای فراموش نشدنی را به نمایش میگذارند", "تیم ما برای رسیدن به این موفقیت تلاش های شبانه روزی زیادی انجام داد", 
    "حفظ محیط زیست وظیفه تک تک ما برای نسل های آینده است", "موفقیت در زندگی نیازمند تلاش پشتکار و کمی شانس است", 
    "اینترنت اشیاء دنیایی را متصور میشود که همه چیز به هم متصل است", "بزرگترین ماجراجویی که میتوانی داشته باشی زندگی کردن رویاهایت است", 
    "برای حل مسائل پیچیده گاهی باید از زوایای مختلف به آنها نگاه کرد", "تاریخ پر از درس هایی است که میتوانیم برای ساختن آینده ای بهتر از آنها بیاموزیم", 
    "هوش مصنوعی به سرعت در حال تغییر چهره جهان ما است", "یک دوست خوب گنجی گرانبها در فراز و نشیب های زندگی است", "سفر کردن به نقاط مختلف جهان دیدگاه انسان را گسترش میدهد", 
    "ورزش منظم کلید اصلی برای داشتن بدنی سالم و روحی شاداب است", "موسیقی زبان مشترک تمام انسان ها در سراسر کره زمین است", 
    "هیچگاه برای یادگیری و شروع یک مسیر جدید دیر نیست", "احترام به عقاید دیگران حتی اگر با آنها مخالف باشیم نشانه بلوغ است", 
    "تغییر تنها پدیده ثابت در جهان هستی است باید خود را با آن وفق دهیم", "صبر و شکیبایی در برابر مشکلات آنها را در نهایت حل شدنی میکند", 
    "خلاقیت یعنی دیدن چیزی که دیگران نمیبینند و انجام کاری که دیگران جراتش را ندارند", "شادی واقعی در داشتن چیزهای زیاد نیست بلکه در لذت بردن از چیزهایی است که داریم", 
    "صداقت و راستگویی سنگ بنای هر رابطه پایدار و موفقی است", "کهکشان راه شیری تنها یکی از میلیاردها کهکشان موجود در کیهان است", 
    "برای ساختن یک ربات پیشرفته به دانش برنامه نویسی و الکترونیک نیاز است", "امنیت سایبری در دنیای دیجیتال امروز از اهمیت فوق العاده ای برخوردار است", 
    "هرگز قدرت یک ایده خوب را دست کم نگیر میتواند دنیا را تغییر دهد", "کار گروهی و همکاری میتواند منجر به نتایجی شگفت انگیز شود", 
    "شکست بخشی از مسیر موفقیت است از آن درس بگیرید و دوباره تلاش کنید", "جنگل های آمازون به عنوان ریه های کره زمین شناخته میشوند", 
    "کوه اورست بلندترین قله جهان در رشته کوه هیمالیا قرار دارد", "دیوار بزرگ چین یکی از شگفتی های ساخت بشر در طول تاریخ است", 
    "اهرام ثلاثه مصر نماد تمدن باستانی و معماری شگفت انگیز آن دوران هستند", "خورشید گرفتگی زمانی رخ میدهد که ماه بین زمین و خورشید قرار بگیرد", 
    "آب مایه حیات است و باید در مصرف آن صرفه جویی کنیم", "زنبورهای عسل نقش بسیار مهمی در گرده افشانی و حیات گیاهان دارند", 
    "بازیافت زباله به حفظ منابع طبیعی و کاهش آلودگی کمک میکند", "کهکشان آندرومدا نزدیکترین کهکشان مارپیچی به کهکشان ما است", 
    "سرعت نور بالاترین سرعت ممکن در جهان هستی محسوب میشود", "هر انسان دارای اثر انگشت منحصر به فردی است که او را از دیگران متمایز میکند", 
    "یوزپلنگ سریعترین حیوان روی خشکی است و میتواند به سرعت بالایی برسد", "قلب یک انسان بالغ به طور متوسط صد هزار بار در روز میتپد", 
    "خواب کافی برای سلامت جسم و روان و عملکرد بهتر مغز ضروری است", "ویتامین دی با قرار گرفتن در معرض نور خورشید در بدن تولید میشود", 
    "خنده بهترین دارو برای کاهش استرس و تقویت سیستم ایمنی بدن است", "یادگیری موسیقی میتواند به بهبود حافظه و هماهنگی اعضای بدن کمک کند", 
    "ارتباطات ماهواره ای امکان برقراری تماس در سراسر جهان را فراهم کرده است", "فیبر نوری با استفاده از پالس های نوری داده ها را با سرعت بالا منتقل میکند", 
    "واقعیت مجازی تجربه ای فراگیر از یک دنیای شبیه سازی شده را ارائه میدهد", "چاپگرهای سه بعدی قادر به ساخت اشیاء فیزیکی از روی مدل های دیجیتال هستند", 
    "خودروهای الکتریکی با هدف کاهش آلودگی هوا در حال گسترش هستند", "انرژی هسته ای از شکافت اتم ها برای تولید برق استفاده میکند", "قطره قطره جمع گردد وانگهی دریا شود", 
    "آینده ساختنی است نه یافتنی پس باید برای آن تلاش کرد", "بهترین زمان برای کاشتن یک درخت بیست سال پیش بود زمان بعدی همین امروز است", 
    "برای دیدن رنگین کمان باید هم باران را تحمل کنی هم آفتاب را", "موفقیت مجموعه ای از تلاش های کوچک است که هر روز تکرار میشوند", 
    "تنها محدودیت های زندگی آنهایی هستند که خودمان برای خودمان ایجاد میکنیم", "به جای نگرانی در مورد چیزهایی که نمیتوانی کنترل کنی روی چیزهایی که میتوانی تغییر دهی تمرکز کن", 
    "شجاعت نبودن ترس نیست بلکه عمل کردن با وجود ترس است", "یک سفر هزار کیلومتری با اولین قدم آغاز میشود", "زندگی مثل دوچرخه سواری است برای حفظ تعادل باید به حرکت ادامه دهی", 
    "انسان های موفق همیشه به دنبال فرصت هایی برای کمک به دیگران هستند", "هدف گذاری اولین قدم برای تبدیل نادیدنی ها به دیدنی ها است", 
    "راز پیشرفت شروع کردن است پس منتظر زمان مناسب نمان", "اگر میخواهی متفاوت باشی باید کارهای متفاوتی انجام دهی", "اشتباه کردن بخشی از انسان بودن است مهم درس گرفتن از آنها است", 
    "اجازه نده سر و صدای عقاید دیگران صدای درونی تو را خاموش کند", "خوشبختی یک مسیر است نه یک مقصد از لحظات خود لذت ببر", 
    "تنها راه انجام دادن کارهای بزرگ دوست داشتن کاری است که انجام میدهی", "فرصت ها مانند طلوع خورشید هستند اگر زیاد صبر کنی آنها را از دست میدهی", 
    "استعداد ذاتی فقط یک شروع است باید با تلاش آن را پرورش دهی", "با افکار مثبت دنیای خود را زیباتر کن چون زندگی انعکاس افکار تو است", 
    "برای رسیدن به قله باید سختی های مسیر را تحمل کرد", "سکوت گاهی بهترین پاسخ به سوالات بی معنی است", "برای داشتن دوست وفادار باید خودت یک دوست وفادار باشی", 
    "امید مانند چراغی در تاریکی مسیر را برایت روشن میکند", "کتاب ها بهترین دوستان خاموش ما هستند که هرگز ما را ترک نمیکنند", 
    "دانش قدرتی است که هیچکس نمیتواند آن را از تو بگیرد", "گذشته را نمیتوان تغییر داد اما آینده هنوز در دستان تو است", 
    "تفاوت بین یک فرد موفق و دیگران کمبود قدرت نیست بلکه کمبود اراده است", "انسان های بزرگ درباره ایده ها صحبت میکنند انسان های متوسط درباره رویدادها و انسان های کوچک درباره دیگران", 
    "برای پرواز کردن لازم نیست حتما بال داشته باشی داشتن اراده و رویا کافی است", "ساده ترین کارها اغلب درست ترین آنها هستند", 
    "تمرین زیاد باعث میشود کارهای سخت آسان به نظر برسند", "یک ذهن آرام میتواند قوی ترین طوفان ها را پشت سر بگذارد", 
    "هرگز اجازه نده دیروز بخش زیادی از امروز تو را به خود اختصاص دهد", "اگر به دنبال نتایج متفاوت هستی باید روش های متفاوتی را امتحان کنی", 
    "صبر کلید موفقیت در تمام مراحل زندگی است", "سعی نکن انسان موفقی باشی بلکه سعی کن انسان با ارزشی باشی", "راز شاد زیستن در لذت بردن از چیزهای کوچک است", 
    "همیشه به یاد داشته باش که مسیر موفقیت در حال ساخت است نه یک جاده آماده", "یک لبخند میتواند شروع یک دوستی زیبا باشد", 
    "اگر میخواهی دنیا را تغییر دهی از مرتب کردن تخت خودت شروع کن", "بخشیدن دیگران به معنای فراموش کردن گذشته نیست بلکه به معنای ساختن آینده ای بهتر است", 
    "مهربانی زبانی است که ناشنوایان میتوانند بشنوند و نابینایان میتوانند ببینند", "هر روز یک فرصت جدید برای شروع دوباره و بهتر شدن است", 
    "سعی نکن در برابر طوفان مقاومت کنی یاد بگیر در باران برقصی", "زندگی یک بوم نقاشی است سعی کن آن را با رنگ های شاد رنگ آمیزی کنی", 
    "اگر بتوانی چیزی را رویاپردازی کنی پس حتما میتوانی آن را انجام دهی", "مهم نیست چقدر آهسته حرکت میکنی تا زمانی که متوقف نشوی پیشرفت خواهی کرد", 
    "یک شمع میتواند هزاران شمع دیگر را روشن کند بدون آنکه از عمرش کاسته شود", "شادی زمانی دوچندان میشود که آن را با دیگران تقسیم کنی", 
    "بهترین راه برای پیش بینی آینده ساختن آن است", "هرگز برای تبدیل شدن به آن کسی که میتوانستی باشی دیر نیست", 
    "ذهن انسان مانند یک باغ است هرچه در آن بکاری همان را درو میکنی", "یک گفتگو صادقانه میتواند بسیاری از مشکلات را حل کند", 
    "سخاوت یعنی بخشیدن بیش از توانایی ات و غرور یعنی گرفتن کمتر از نیازت", "کسانی که به اندازه کافی دیوانه هستند که فکر کنند میتوانند دنیا را تغییر دهند همان هایی هستند که این کار را میکنند", 
    "انتقام گرفتن تو را با دشمنت برابر میکند اما بخشیدن او تو را برتر از او قرار میدهد", "کسی که سوال میپرسد برای یک دقیقه نادان است اما کسی که سوال نمیپرسد برای همیشه نادان باقی میماند", 
    "زندگی کوتاهتر از آن است که وقت خود را صرف متنفر بودن از دیگران کنی", "برای ساختن یک خانه محکم باید پایه های آن را قوی بنا کنی", 
    "یک کتاب خوب میتواند دیدگاه تو را نسبت به کل دنیا تغییر دهد", "قدرت واقعی در کنترل کردن دیگران نیست بلکه در کنترل کردن خود است", 
    "هرگز ارزش یک لحظه را نمیفهمی تا زمانی که به یک خاطره تبدیل شود", "برای شنا کردن در جهت مخالف رودخانه باید قویتر از جریان آب باشی", 
    "یک قهرمان واقعی کسی است که با وجود تمام سختی ها دوباره برمیخیزد", "آرامش را در درون خودت پیدا کن نه در دنیای بیرون", 
    "اولین قدم برای رسیدن به هر جایی تصمیم گرفتن برای حرکت است", "اگر به زیبایی اعتقاد داشته باشی آن را در همه جا خواهی دید", 
    "هیچ چیز ارزشمندی به آسانی به دست نمی آید", "یک دروغ ممکن است برای مدتی تو را نجات دهد اما در نهایت حقیقت آشکار میشود", 
    "برای شنیدن صدای فرصت ها باید گوش هایت را تیز کنی", "یک رهبر واقعی راه را بلد است راه را میرود و راه را نشان میدهد", 
    "هرگز اجازه نده موفقیت هایت تو را مغرور و شکست هایت تو را ناامید کند", "زیبایی واقعی در سادگی نهفته است", 
    "یک دوست خوب در روزهای سخت مانند آینه و در روزهای خوب مانند سایه است", "برای رسیدن به نور باید از تاریکی عبور کرد", 
    "دانش بدون عمل مانند ابری بی باران است", "زندگی یک بازی است سعی کن از آن لذت ببری و جوانمردانه بازی کنی", 
    "اعتماد مانند یک کاغذ است اگر مچاله شود دیگر هرگز صاف نخواهد شد", "یک قلب مهربان از تمام معابد و مساجد دنیا مقدس تر است", 
    "آینده متعلق به کسانی است که به زیبایی رویاهایشان ایمان دارند", "جاده ابریشم یک مسیر تجاری باستانی برای اتصال شرق و غرب بود", 
    "کوه دماوند بلندترین قله آتشفشانی در خاورمیانه است", "آرش کمانگیر مرز ایران و توران را با پرتاب یک تیر مشخص کرد", 
    "خلیج فارس یکی از مهمترین آبراه های استراتژیک جهان به شمار میرود", "راز تغییر کردن در این است که تمام انرژی خود را روی ساختن عادت های جدید بگذاری"
]

# --- تنظیمات لاگ ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- مدیریت دیتابیس (بدون تغییر) ---
DATABASE_URL = os.environ.get("DATABASE_URL")
def get_db_connection():
    try: return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def setup_database():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, first_name VARCHAR(255), username VARCHAR(255), start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());")
                cur.execute("CREATE TABLE IF NOT EXISTS groups (group_id BIGINT PRIMARY KEY, title VARCHAR(255), member_count INT, added_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());")
                cur.execute("CREATE TABLE IF NOT EXISTS start_message (id INT PRIMARY KEY, message_id BIGINT, chat_id BIGINT);")
                cur.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id BIGINT PRIMARY KEY);")
                cur.execute("CREATE TABLE IF NOT EXISTS banned_groups (group_id BIGINT PRIMARY KEY);")
            conn.commit()
            logger.info("Database setup complete.")
        except Exception as e: logger.error(f"Database setup failed: {e}")
        finally: conn.close()

# --- توابع کمکی ---
async def is_owner(user_id: int) -> bool: return user_id in OWNER_IDS
async def is_group_admin(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_owner(user_id): return True
    admins = await context.bot.get_chat_administrators(chat_id)
    return user_id in {admin.user.id for admin in admins}
def convert_persian_to_english_numbers(text: str) -> str:
    if not text: return ""
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

# --- مدیریت وضعیت بازی‌ها ---
active_games = {'guess_number': {}, 'dooz': {}, 'hangman': {}, 'typing': {}, 'hokm': {}}
active_gharch_games = {}

# --- ##### تغییر کلیدی: منطق جدید عضویت اجباری و بن ##### ---
async def check_ban_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """چک می‌کند که آیا کاربر یا گروه بن شده است یا خیر. اگر گروه بن باشد، ربات خارج می‌شود."""
    user = update.effective_user
    chat = update.effective_chat
    if not user: return True # اگر کاربری وجود نداشت، بن شده در نظر بگیر

    conn = get_db_connection()
    if not conn: return False # اگر دیتابیس وصل نشد، فرض بر عدم بن بودن است
    
    is_banned = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM banned_users WHERE user_id = %s;", (user.id,))
            if cur.fetchone():
                is_banned = True
            
            if not is_banned and chat.type != 'private':
                cur.execute("SELECT 1 FROM banned_groups WHERE group_id = %s;", (chat.id,))
                if cur.fetchone():
                    is_banned = True
                    try:
                        await context.bot.leave_chat(chat.id)
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Error checking ban status: {e}")
    finally:
        conn.close()
    
    return is_banned

async def check_join_for_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    این تابع فقط برای **پیوستن** به بازی‌های کارتی استفاده می‌شود و در صورت عدم عضویت، الرت می‌دهد.
    """
    user = update.effective_user
    if not user or await is_owner(user.id):
        return True

    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user.id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logger.warning(f"Could not check channel membership for alert: {user.id}: {e}")

    if update.callback_query:
        await update.callback_query.answer(
            " @RHINOSOUL_TM برای پیوستن به بازی باید در کانال عضو شوید",
            show_alert=True
        )
    return False

async def check_forced_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    عضویت کاربر در کانال را چک می‌کند. اگر عضو نباشد، پیام عضویت ارسال کرده و False برمی‌گرداند.
    این تابع فقط برای بازی‌هایی که نیاز به عضویت دارند استفاده می‌شود.
    """
    user = update.effective_user
    if not user or await is_owner(user.id):
        return True

    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user.id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logger.warning(f"Could not check channel membership for {user.id}: {e}")

    keyboard = [[InlineKeyboardButton(" عضویت در کانال ", url=f"https://t.me/{FORCED_JOIN_CHANNEL.lstrip('@')}")]]
    text = f"❗️{user.mention_html()}، برای استفاده از این بخش ابتدا باید در کانال ما عضو شوی."
    
    # تشخیص اینکه پاسخ به پیام باشد یا به کلیک روی دکمه
    if update.callback_query:
        await update.callback_query.answer(
            " @RHINOSOUL_TM برای ادامه بازی باید در کانال عضو شوید",
            show_alert=True
        )
    elif update.message:
        await update.message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode=ParseMode.HTML
        )
        
    return False

async def rsgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور اصلی برای نمایش پنل بازی‌ها با بررسی اولیه عضویت و به صورت اختصاصی."""
    if await check_ban_status(update, context):
        return
    
    user = update.effective_user
    user_id = user.id  # شناسه کاربری که دستور را زده است
    is_member = False

    if await is_owner(user_id):
        is_member = True
    else:
        try:
            member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user_id)
            if member.status in ['member', 'administrator', 'creator']:
                is_member = True
        except Exception:
            is_member = False 

    if is_member:
        text = f"🎮 {user.first_name} عزیز، به پنل بازی خوش آمدید.\n\nلطفا دسته بندی مورد نظر خود را انتخاب کنید:"
        
        # شناسه کاربر به انتهای callback_data اضافه می‌شود تا پنل اختصاصی شود
        keyboard = [
            [InlineKeyboardButton("🏆 بازی‌های کارتی و گروهی", callback_data=f"rsgame_cat_board_{user_id}")],
            [InlineKeyboardButton("✍️ بازی‌های تایپی و سرعتی", callback_data=f"rsgame_cat_typing_{user_id}")],
            [InlineKeyboardButton("🤫 بازی‌های ناشناس (ویژه ادمین)", callback_data=f"rsgame_cat_anon_{user_id}")],
            [InlineKeyboardButton("✖️ بستن پنل", callback_data=f"rsgame_close_{user_id}")]
        ]
        
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        text = "❗️برای استفاده از بازی‌ها، لطفا ابتدا در کانال ما عضو شوید و سپس دکمه «عضو شدم» را بزنید."
        keyboard = [
            [InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{FORCED_JOIN_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="rsgame_check_join")]
        ]
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def rsgame_check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی مجدد عضویت پس از کلیک روی دکمه 'عضو شدم'."""
    query = update.callback_query
    user = query.from_user
    
    try:
        member = await context.bot.get_chat_member(chat_id=FORCED_JOIN_CHANNEL, user_id=user.id)
        if member.status in ['member', 'administrator', 'creator']:
            await query.answer("عضویت شما تایید شد!")
            # حالا که عضویت تایید شد، پنل اصلی را به او نشان می‌دهیم
            await rsgame_command(update, context)
        else:
            await query.answer("شما هنوز در کانال عضو نشده‌اید!", show_alert=True)
    except Exception:
        await query.answer("خطایی در بررسی عضویت رخ داد. لطفاً لحظاتی دیگر دوباره تلاش کنید.", show_alert=True)

async def rsgame_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌های پنل اصلی بازی‌ها و بررسی مالکیت پنل."""
    query = update.callback_query
    
    # -- بخش جدید: بررسی مالکیت پنل --
    data = query.data.split('_')
    try:
        # آخرین بخش callback_data همیشه آیدی کاربر است
        target_user_id = int(data[-1]) 
    except (ValueError, IndexError):
        await query.answer("خطا: این دکمه منقضی شده است. لطفاً دوباره دستور را ارسال کنید.", show_alert=True)
        return

    clicker_user_id = query.from_user.id

    if clicker_user_id != target_user_id:
        await query.answer("این پنل برای شما نیست!", show_alert=True)
        return
    # -- پایان بخش جدید --

    await query.answer()
    
    if await check_ban_status(update, context):
        return

    action_type = data[1]
    
    if len(data) > 2 and data[2] == "main":
        await rsgame_command(update, context)
        return
        
    # این بخش به تابع جداگانه منتقل شد، پس اینجا نیازی به آن نیست
    # if action_type == "close":
    #    await query.edit_message_text("پنل بسته شد.")
    #    return

    category = data[2]
    user_id = target_user_id
    text = "لطفا بازی مورد نظر خود را انتخاب کنید:"
    keyboard = []
    
    if category == "board":
        text = " دسته بندی بازی‌های کارتی و گروهی:\n\n(عضویت در کانال برای پیوستن به بازی الزامی است)"
        keyboard = [
            [InlineKeyboardButton(" حکم ۲ نفره ", callback_data=f"hokm_start_2p_{user_id}")],
            [InlineKeyboardButton(" حکم ۴ نفره ", callback_data=f"hokm_start_4p_{user_id}")],
            [InlineKeyboardButton(" دوز (دو نفره) ", callback_data=f"dooz_start_2p_{user_id}")],
            [InlineKeyboardButton(" بازگشت ", callback_data=f"rsgame_cat_main_{user_id}")]
        ]
    elif category == "typing":
        text = " دسته بندی بازی‌های تایپی و سرعتی (بدون اجبار عضویت):"
        keyboard = [
            [InlineKeyboardButton(" حدس کلمه ", callback_data=f"hads_kalame_start_{user_id}")],
            [InlineKeyboardButton(" تایپ سرعتی ", callback_data=f"type_start_{user_id}")],
            [InlineKeyboardButton(" حدس عدد (ویژه ادمین)", callback_data=f"hads_addad_start_{user_id}")],
            [InlineKeyboardButton(" بازگشت ", callback_data=f"rsgame_cat_main_{user_id}")]
        ]
    elif category == "anon":
        if not await is_group_admin(clicker_user_id, query.message.chat.id, context):
            await query.answer("این بخش فقط برای مدیران گروه در دسترس است.", show_alert=True)
            return
            
        text = " دسته بندی بازی‌های ناشناس (ویژه ادمین):"
        keyboard = [
            [InlineKeyboardButton(" اعتراف (متن پیش‌فرض) ", callback_data=f"eteraf_start_default_{user_id}")],
            [InlineKeyboardButton(" اعتراف (متن سفارشی) ", callback_data=f"eteraf_start_custom_{user_id}")],
            [InlineKeyboardButton(" قارچ (با نظارت گاد) ", callback_data=f"gharch_start_{user_id}")],
            [InlineKeyboardButton(" بازگشت ", callback_data=f"rsgame_cat_main_{user_id}")]
        ]
        
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --------------------------- GAME: HOKM (بدون تغییر در منطق اصلی) ---------------------------
# توابع کمکی حکم (card_to_persian, create_deck, ...) همانند قبل باقی می‌مانند
# ... (کد بازی حکم در اینجا قرار می‌گیرد - بدون تغییر)
import asyncio

async def rsgame_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل بازی را می‌بندد."""
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("پنل بسته شد.")
    except Exception:
        # اگر پیام خیلی قدیمی باشد یا مشکلی در ویرایش پیش بیاید، آن را حذف می‌کنیم
        try:
            await query.delete_message()
        except Exception:
            pass

def create_deck():
    """یک دسته کارت مرتب شده ۵۲تایی ایجاد و آن را بُر می‌زند."""
    suits = ['S', 'H', 'D', 'C']  # Spades, Hearts, Diamonds, Clubs
    ranks = list(range(2, 15))  # 2-10, J(11), Q(12), K(13), A(14)
    deck = [f"{s}{r}" for s in suits for r in ranks]
    random.shuffle(deck)
    return deck

def card_to_persian(card):
    """کارت را به فرمت فارسی با ایموجی تبدیل می‌کند."""
    if not card: return "🃏"
    suits = {'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️'}
    ranks = {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
    suit, rank = card[0], int(card[1:])
    # نمایش رنک کارت یا حرف معادل آن
    rank_display = str(ranks.get(rank, rank))
    return f"{suits[suit]} {rank_display}"

def get_card_value(card, hokm_suit, trick_suit):
    """ارزش عددی یک کارت را برای مقایسه و تعیین برنده دست محاسبه می‌کند."""
    suit, rank = card[0], int(card[1:])
    value = rank
    if suit == hokm_suit:
        value += 200  # کارت‌های حکم بالاترین ارزش را دارند
    elif suit == trick_suit:
        value += 100  # کارت‌های خال زمین ارزش بیشتری از سایر خال‌ها دارند
    return value

async def render_hokm_board(game: dict, context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع صفحه بازی (متن و دکمه‌ها) را بر اساس وضعیت فعلی بازی برای همه تولید می‌کند.
    (نسخه اصلاح شده برای نمایش دقیق کارت‌ها)
    """
    game_id = game['message_id']
    keyboard = []
    
    p_names = [p['name'] for p in game['players']]
    p_ids = [p['id'] for p in game['players']]
    
    # دیکشنری برای نگهداری کارت‌های روی میز تا هر کارت دقیقاً جلوی بازیکن خودش قرار گیرد
    table_cards_map = {pid: "➖" for pid in p_ids}
    for play in game.get('current_trick', []):
        table_cards_map[play['player_id']] = card_to_persian(play['card'])

    # --- بخش نمایش بازیکنان و کارت‌های روی میز ---
    if game['mode'] == '4p':
        team_a_text = f"🔴 تیم 1: {p_names[0]} و {p_names[2]}"
        team_b_text = f"🔵 تیم 2: {p_names[1]} و {p_names[3]}"
        
        board_layout = [
            [InlineKeyboardButton(team_a_text, callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton(team_b_text, callback_data=f"hokm_noop_{game_id}")],
            [InlineKeyboardButton("بازیکن", callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton("کارت بازی شده", callback_data=f"hokm_noop_{game_id}")],
        ]
        # نمایش نام هر بازیکن در کنار کارتی که بازی کرده است
        for i in range(4):
            board_layout.append([
                InlineKeyboardButton(p_names[i], callback_data=f"hokm_noop_{game_id}"), 
                InlineKeyboardButton(table_cards_map[p_ids[i]], callback_data=f"hokm_noop_{game_id}")
            ])
        keyboard.extend(board_layout)
    else: # حالت دو نفره
        board_layout = []
        for i in range(2):
            board_layout.append([
                InlineKeyboardButton(p_names[i], callback_data=f"hokm_noop_{game_id}"), 
                InlineKeyboardButton(table_cards_map[p_ids[i]], callback_data=f"hokm_noop_{game_id}")
            ])
        keyboard.extend(board_layout)

    # --- بخش نمایش وضعیت و امتیازات ---
    hokm_suit_fa = card_to_persian(f"{game['hokm_suit']}2")[0] if game.get('hokm_suit') else '❓'
    hakem_name = game.get('hakem_name', '...')
    
    if game['mode'] == '4p':
        trick_score_text = f"دست: 🔴 {game['trick_scores']['A']} - {game['trick_scores']['B']} 🔵"
        game_score_text = f"امتیاز کل: 🔴 {game['game_scores']['A']} - {game['game_scores']['B']} 🔵"
    else:
        trick_score_text = f"دست: {p_names[0]} {game['trick_scores'][p_ids[0]]} - {game['trick_scores'][p_ids[1]]} {p_names[1]}"
        game_score_text = f"امتیاز کل: {p_names[0]} {game['game_scores'][p_ids[0]]} - {game['game_scores'][p_ids[1]]} {p_names[1]}"

    keyboard.append([InlineKeyboardButton(f"حاکم: {hakem_name}", callback_data=f"hokm_noop_{game_id}"), InlineKeyboardButton(f"حکم: {hokm_suit_fa}", callback_data=f"hokm_noop_{game_id}")])
    keyboard.append([InlineKeyboardButton(trick_score_text, callback_data=f"hokm_noop_{game_id}")])
    keyboard.append([InlineKeyboardButton(game_score_text, callback_data=f"hokm_noop_{game_id}")])

    # --- بخش دکمه‌های کنترلی ---
    keyboard.append([InlineKeyboardButton("🃏 نمایش دست من (خصوصی)", callback_data=f"hokm_showhand_{game_id}")])

    # نمایش دکمه‌های انتخاب حکم فقط برای حاکم
    if game['status'] == 'hakem_choosing' and game.get('turn_index') is not None and game['players'][game['turn_index']]['id'] == game.get('hakem_id'):
        suit_map = {'♠️': 'S', '♥️': 'H', '♦️': 'D', '♣️': 'C'}
        choose_buttons = [InlineKeyboardButton(emoji, callback_data=f"hokm_choose_{game_id}_{char}") for emoji, char in suit_map.items()]
        keyboard.append(choose_buttons)
    # نمایش دکمه‌های بازی فقط برای بازیکنی که نوبتش است
    elif game['status'] == 'playing' and game.get('turn_index') is not None:
        current_player_id = game['players'][game['turn_index']]['id']
        if current_player_id in game['hands']:
            player_hand = sorted(game['hands'][current_player_id])
            card_buttons = [InlineKeyboardButton(str(i + 1), callback_data=f"hokm_play_{game_id}_{i}") for i in range(len(player_hand))]
            # تقسیم دکمه‌ها در سطرهای ۷ تایی برای زیبایی
            for i in range(0, len(card_buttons), 7):
                keyboard.append(card_buttons[i:i+7])
    
    return InlineKeyboardMarkup(keyboard)

async def hokm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    
    # این تابع را از کد اصلی خودتان فراخوانی کنید
    # if await check_ban_status(update, context): return
        
    data = query.data.split('_'); action = data[1]

    if action == "start":
        await query.answer()
        mode = data[2]
        max_players = 4 if mode == '4p' else 2

        if chat_id not in active_games['hokm']:
            active_games['hokm'][chat_id] = {}
        
        sent_message = await query.message.reply_text(
            f"در حال ساخت بازی حکم {max_players} نفره..."
        )
        
        game_id = sent_message.message_id 
        
        game = {
            "status": "joining", 
            "mode": mode, 
            "players": [{'id': user.id, 'name': user.first_name}], 
            "message_id": game_id,
            "hands": {}, "deck": [], "hakem_id": None
        }
        active_games['hokm'][chat_id][game_id] = game
        
        keyboard = [[InlineKeyboardButton(f"پیوستن به بازی (1/{max_players})", callback_data=f"hokm_join_{game_id}")]]
        await sent_message.edit_text(
            f"بازی حکم {max_players} نفره توسط {user.mention_html()} ساخته شد! منتظر بازیکنان...\n @RHINOSOUL_TM برای شرکت در بازی عضو کانال شوید", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    game_id = int(data[2])
    if chat_id not in active_games['hokm'] or game_id not in active_games['hokm'][chat_id]:
        await query.answer("این بازی دیگر فعال نیست.", show_alert=True)
        try: await query.edit_message_text("این بازی تمام شده است.")
        except: pass
        return
    
    game = active_games['hokm'][chat_id][game_id]

    if action == "join":
        # این تابع را از کد اصلی خودتان فراخوانی کنید
        # if not await check_join_for_alert(update, context): return

        if any(p['id'] == user.id for p in game['players']): 
            return await query.answer("شما قبلاً به بازی پیوسته‌اید!", show_alert=True)
        max_players = 4 if game['mode'] == '4p' else 2
        if len(game['players']) >= max_players: 
            return await query.answer("ظرفیت بازی تکمیل است.", show_alert=True)
        
        await query.answer()
        game['players'].append({'id': user.id, 'name': user.first_name})
        num_players = len(game['players'])

        if num_players < max_players:
            keyboard = [[InlineKeyboardButton(f"پیوستن به بازی ({num_players}/{max_players})", callback_data=f"hokm_join_{game_id}")]]
            await query.edit_message_text(f"بازی حکم (ID: {game_id})\nبازیکنان وارد شده: {num_players}/{max_players}\n @RHINOSOUL_TM برای شرکت در بازی عضو کانال شوید", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            p_ids = [p['id'] for p in game['players']]
            game.update({
                "status": "dealing_first_5", "deck": create_deck(), "hands": {pid: [] for pid in p_ids},
                "hakem_id": None, "hakem_name": None, "turn_index": 0, "hokm_suit": None, "current_trick": [],
                "trick_scores": {'A': 0, 'B': 0} if game['mode'] == '4p' else {pid: 0 for pid in p_ids},
                "game_scores": game.get('game_scores', {'A': 0, 'B': 0} if game['mode'] == '4p' else {pid: 0 for pid in p_ids})
            })

            for _ in range(5):
                for p in game['players']: game['hands'][p['id']].append(game['deck'].pop(0))
            
            hakem_p = next((p for p in game['players'] if 'S14' in game['hands'][p['id']]), game['players'][0])
            game.update({"hakem_id": hakem_p['id'], "hakem_name": hakem_p['name'], "status": 'hakem_choosing'})
            game['turn_index'] = next(i for i, p in enumerate(game['players']) if p['id'] == hakem_p['id'])
            
            reply_markup = await render_hokm_board(game, context)
            await query.edit_message_text(f"بازیکنان کامل شدند!\nحاکم: {game['hakem_name']}\n\nنوبت شماست که حکم را انتخاب کنید.", reply_markup=reply_markup)
    
    elif action == "choose":
        if user.id != game.get('hakem_id'): return await query.answer("شما حاکم نیستید!", show_alert=True)
        if game['status'] != 'hakem_choosing': return await query.answer("الان زمان انتخاب حکم نیست!", show_alert=True)
        
        await query.answer()
        game['hokm_suit'] = data[3]
        
        for p in game['players']:
            while len(game['hands'][p['id']]) < 13: 
                if not game['deck']: break
                game['hands'][p['id']].append(game['deck'].pop(0))
        
        game['status'] = 'playing'
        game['turn_index'] = next(i for i, p in enumerate(game['players']) if p['id'] == game['hakem_id'])
        turn_player_name = game['players'][game['turn_index']]['name']
        
        reply_markup = await render_hokm_board(game, context)
        await query.edit_message_text(f"بازی شروع شد! حکم: {card_to_persian(game['hokm_suit']+'2')[0]}\n\nنوبت {turn_player_name} است.", reply_markup=reply_markup)

    elif action == "showhand":
        if not any(p['id'] == user.id for p in game['players']): return await query.answer("شما بازیکن این مسابقه نیستید!", show_alert=True)
        hand = sorted(game['hands'].get(user.id, []))
        hand_str = "\n".join([f"{i+1}. {card_to_persian(c)}" for i, c in enumerate(hand)]) or "شما کارتی در دست ندارید."
        await query.answer(f"دست شما:\n{hand_str}", show_alert=True)

    elif action == "play":
        if user.id != game['players'][game['turn_index']]['id']: return await query.answer("نوبت شما نیست!", show_alert=True)
        
        card_index = int(data[3])
        hand = sorted(game['hands'][user.id]) 
        if not (0 <= card_index < len(hand)): return await query.answer("شماره کارت نامعتبر است.", show_alert=True)
        
        card_played = hand[card_index]
        if game['current_trick']:
            trick_suit = game['current_trick'][0]['card'][0]
            if any(c.startswith(trick_suit) for c in hand) and not card_played.startswith(trick_suit):
                return await query.answer(f"شما باید از خال زمین ({card_to_persian(trick_suit+'2')[0]}) بازی کنید!", show_alert=True)

        await query.answer()
        game['hands'][user.id].remove(card_played)
        game['current_trick'].append({'player_id': user.id, 'card': card_played})

        num_players = len(game['players'])
        # --- اگر دست (Trick) هنوز تکمیل نشده باشد ---
        if len(game['current_trick']) < num_players:
            game['turn_index'] = (game['turn_index'] + 1) % num_players
            turn_player_name = game['players'][game['turn_index']]['name']
            reply_markup = await render_hokm_board(game, context)
            await query.edit_message_text(f"حکم: {card_to_persian(game['hokm_suit']+'2')[0]}\n\nنوبت {turn_player_name} است.", reply_markup=reply_markup)
            return

        # --- اگر دست (Trick) تکمیل شده باشد ---
        trick_suit = game['current_trick'][0]['card'][0]
        winner_play = max(game['current_trick'], key=lambda p: get_card_value(p['card'], game['hokm_suit'], trick_suit))
        winner_id = winner_play['player_id']
        winner_name = next(p['name'] for p in game['players'] if p['id'] == winner_id)
        
        if game['mode'] == '4p':
            winner_team = 'A' if winner_id in [game['players'][0]['id'], game['players'][2]['id']] else 'B'
            game['trick_scores'][winner_team] += 1
            round_over = game['trick_scores']['A'] == 7 or game['trick_scores']['B'] == 7
        else:
            game['trick_scores'][winner_id] += 1
            round_over = any(score == 7 for score in game['trick_scores'].values())

        # نوبت شروع دست بعدی با برنده این دست است
        game['turn_index'] = next(i for i, p in enumerate(game['players']) if p['id'] == winner_id)
        
        # نمایش موقت نتیجه دست و سپس پاک کردن کارت‌های روی میز
        trick_cards_for_display = game['current_trick'][:]
        game['current_trick'] = []
        
        turn_player_name = game['players'][game['turn_index']]['name']
        temp_game_state = game.copy(); temp_game_state['current_trick'] = trick_cards_for_display
        temp_reply_markup = await render_hokm_board(temp_game_state, context)
        await query.edit_message_text(f"برنده این دست: {winner_name}\n\nنوبت شروع دست بعدی با {turn_player_name} است.", reply_markup=temp_reply_markup)
        
        await asyncio.sleep(2.5)

        # --- اگر دور (Round) تمام نشده باشد ---
        if not round_over:
            reply_markup = await render_hokm_board(game, context)
            await query.edit_message_text(f"حکم: {card_to_persian(game['hokm_suit']+'2')[0]}\n\nنوبت {turn_player_name} است.", reply_markup=reply_markup)
        # --- اگر دور (Round) تمام شده باشد ---
        else:
            if game['mode'] == '4p':
                winning_team_name = 'A' if game['trick_scores']['A'] == 7 else 'B'
                game['game_scores'][winning_team_name] += 1
                winner_display_name = f"تیم {winning_team_name}"
                game_over = game['game_scores'][winning_team_name] == 7
            else:
                round_winner_id = next(pid for pid, score in game['trick_scores'].items() if score == 7)
                winner_display_name = next(p['name'] for p in game['players'] if p['id'] == round_winner_id)
                game['game_scores'][round_winner_id] += 1
                game_over = any(score == 7 for score in game['game_scores'].values())

            if game_over:
                await query.edit_message_text(f"🏆 **بازی تمام شد!** 🏆\n\nبرنده نهایی: **{winner_display_name}**", parse_mode=ParseMode.MARKDOWN)
                del active_games['hokm'][chat_id][game_id]
                return
            
            # --- منطق تعیین حاکم بعدی بر اساس درخواست شما ---
            current_hakem_index = next(i for i, p in enumerate(game['players']) if p['id'] == game['hakem_id'])
            if game['mode'] == '4p':
                hakem_team = 'A' if current_hakem_index in [0, 2] else 'B'
                if winning_team_name == hakem_team:
                    next_hakem_index = current_hakem_index # حاکم برنده، حاکم باقی می‌ماند
                else:
                    next_hakem_index = (current_hakem_index + 1) % 4 # حاکمیت به نفر بعدی منتقل می‌شود
            else: # 2p
                round_winner_id = next(pid for pid, score in game['trick_scores'].items() if score == 7)
                if round_winner_id == game['hakem_id']:
                    next_hakem_index = current_hakem_index
                else:
                    next_hakem_index = (current_hakem_index + 1) % 2
            
            # ریست کردن بازی برای دور جدید
            p_ids = [p['id'] for p in game['players']]
            game.update({ 
                "status": "dealing_first_5", "deck": create_deck(), 
                "hands": {pid: [] for pid in p_ids},
                "trick_scores": {'A': 0, 'B': 0} if game['mode'] == '4p' else {pid: 0 for pid in p_ids} 
            })
            for _ in range(5):
                for p in game['players']: game['hands'][p['id']].append(game['deck'].pop(0))
            
            game['hakem_id'] = game['players'][next_hakem_index]['id']
            game['hakem_name'] = game['players'][next_hakem_index]['name']
            game['status'] = 'hakem_choosing'
            game['turn_index'] = next_hakem_index

            reply_markup = await render_hokm_board(game, context)
            await query.edit_message_text(f"این دست تمام شد! برنده: {winner_display_name}\n\n-- دور جدید --\nحاکم جدید: {game['hakem_name']}\nمنتظر انتخاب حکم...", reply_markup=reply_markup)
            
    elif action == "noop":
        await query.answer()

# --------------------------- GAME: GUESS THE NUMBER (ConversationHandler - بدون تغییر) ---------------------------
async def hads_addad_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if await check_ban_status(update, context): return ConversationHandler.END
    
    # الرت برای کاربر عادی
    if not await is_group_admin(query.from_user.id, query.message.chat.id, context):
        await query.answer("❌ این بازی فقط توسط مدیران گروه قابل اجراست.", show_alert=True)
        return ConversationHandler.END
        
    if query.message.chat.id in active_games['guess_number']:
        await query.answer("یک بازی حدس عدد در این گروه فعال است.", show_alert=True)
        return ConversationHandler.END
        
    await query.edit_message_text("بازه بازی را مشخص کنید. (مثال: `1-1000`)\nبرای لغو /cancel را ارسال کنید.", parse_mode=ParseMode.MARKDOWN)
    return SELECTING_RANGE

async def receive_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = update.effective_chat
    try:
        min_str, max_str = convert_persian_to_english_numbers(update.message.text).split('-')
        min_range, max_range = int(min_str.strip()), int(max_str.strip())
        if min_range >= max_range: raise ValueError
    except:
        await update.message.reply_text("فرمت اشتباه است. لطفا به این صورت وارد کنید: `عدد کوچک-عدد بزرگ`", parse_mode=ParseMode.MARKDOWN)
        return SELECTING_RANGE
    secret_number = random.randint(min_range, max_range)
    active_games['guess_number'][chat.id] = {"number": secret_number}
    await update.message.reply_text(f"🎲 **بازی حدس عدد شروع شد!** 🎲\n\nیک عدد بین **{min_range}** و **{max_range}** انتخاب شده.", parse_mode=ParseMode.MARKDOWN)
    return GUESSING

async def handle_guess_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    if chat_id not in active_games['guess_number']: return ConversationHandler.END
    guess = int(convert_persian_to_english_numbers(update.message.text))
    secret_number = active_games['guess_number'][chat_id]['number']
    user = update.effective_user
    if guess < secret_number: await update.message.reply_text("بالاتر ⬆️")
    elif guess > secret_number: await update.message.reply_text("پایین‌تر ⬇️")
    else:
        await update.message.reply_text(f"🎉 **تبریک!** {user.mention_html()} برنده شد! 🎉\n\nعدد صحیح **{secret_number}** بود.", parse_mode=ParseMode.HTML)
        del active_games['guess_number'][chat_id]
        return ConversationHandler.END
    return GUESSING

async def cancel_game_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.id in active_games['guess_number']: del active_games['guess_number'][update.effective_chat.id]
    await update.message.reply_text('بازی حدس عدد لغو شد.')
    # بازگشت به پنل اصلی
    await rsgame_command(update, context)
    return ConversationHandler.END

# --------------------------- GAME: DOOZ (TIC-TAC-TOE) - ##### بازنویسی کامل ##### ---------------------------
async def dooz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    
    if await check_ban_status(update, context): return
    
    data = query.data.split('_'); action = data[1]

    if action == "start":
        await query.answer()
        
        if chat_id not in active_games['dooz']:
            active_games['dooz'][chat_id] = {}

        # یک پیام جدید برای این بازی خاص ایجاد می‌کند
        sent_message = await query.message.reply_text(
            f"در حال ساخت بازی دوز..."
        )

        # از آیدی پیام جدید به عنوان شناسه منحصر به فرد بازی استفاده می‌کنیم
        game_id = sent_message.message_id
        
        game = {
            "status": "joining",
            "players_info": [{'id': user.id, 'name': user.first_name, 'symbol': '❌'}],
            "board": [[" "]*3 for _ in range(3)],
            "turn": None
        }
        active_games['dooz'][chat_id][game_id] = game
        
        keyboard = [[InlineKeyboardButton("پیوستن به بازی (1/2)", callback_data=f"dooz_join_{game_id}")]]
        await sent_message.edit_text(
            f"بازی دوز توسط {user.mention_html()} ساخته شد! منتظر حریف...\n @RHINOSOUL_TM برای پیوستن به بازی عضو کانال شوید", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        try:
            await query.message.delete()
        except Exception:
            pass

        return

    game_id = int(data[2])
    if chat_id not in active_games['dooz'] or game_id not in active_games['dooz'][chat_id]:
        await query.answer("این بازی دیگر فعال نیست.", show_alert=True)
        try: await query.edit_message_text("این بازی تمام شده است.")
        except: pass
        return
        
    game = active_games['dooz'][chat_id][game_id]

    if action == "join":
        if not await check_join_for_alert(update, context): return

        if any(p['id'] == user.id for p in game['players_info']):
            return await query.answer("شما قبلاً به بازی پیوسته‌اید!", show_alert=True)
        
        if len(game['players_info']) >= 2:
            return await query.answer("ظرفیت بازی تکمیل است.", show_alert=True)
        
        await query.answer()
        game['players_info'].append({'id': user.id, 'name': user.first_name, 'symbol': '⭕️'})
        game['status'] = 'playing'
        game['turn'] = game['players_info'][0]['id']

        p1 = game['players_info'][0]
        p2 = game['players_info'][1]

        text = f"بازی شروع شد!\n{p1['name']} ({p1['symbol']}) ⚔️ {p2['name']} ({p2['symbol']})\n\nنوبت {p1['name']} است."
        
        keyboard = [[
            InlineKeyboardButton(" ", callback_data=f"dooz_move_{game_id}_{r*3+c}") 
            for c in range(3)] for r in range(3)
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

    elif action == "move":
        if user.id not in [p['id'] for p in game['players_info']]:
            return await query.answer("شما بازیکن این مسابقه نیستید!", show_alert=True)
        if user.id != game['turn']:
            return await query.answer("نوبت شما نیست!", show_alert=True)

        cell_index = int(data[3])
        row, col = divmod(cell_index, 3)
        if game['board'][row][col] != " ":
            return await query.answer("این خانه پر شده است!", show_alert=True)
        
        await query.answer()
        
        current_player = next(p for p in game['players_info'] if p['id'] == user.id)
        symbol = current_player['symbol']
        game['board'][row][col] = symbol
        
        b = game['board']
        win = any(all(c==symbol for c in r) for r in b) or \
              any(all(b[r][c]==symbol for r in range(3)) for c in range(3)) or \
              all(b[i][i]==symbol for i in range(3)) or \
              all(b[i][2-i]==symbol for i in range(3))
        
        is_draw = all(c!=" " for r in b for c in r) and not win
        winner = user.id if win else "draw" if is_draw else None
        
        next_player = next(p for p in game['players_info'] if p['id'] != user.id)
        game['turn'] = next_player['id']
        
        board_rows = []
        for r in range(3):
            row_buttons = []
            for c in range(3):
                row_buttons.append(InlineKeyboardButton(b[r][c], callback_data=f"dooz_move_{game_id}_{r*3+c}"))
            board_rows.append(row_buttons)

        if winner:
            text = "بازی مساوی شد! 🤝" if winner == "draw" else f"بازی تمام شد! برنده: {current_player['name']} 🏆"
            del active_games['dooz'][chat_id][game_id]
            if not active_games['dooz'][chat_id]:
                del active_games['dooz'][chat_id]
        else:
            text = f"نوبت {next_player['name']} ({next_player['symbol']}) است."
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(board_rows), parse_mode=ParseMode.HTML)

# --------------------------- GAME: HADS KALAME (با جان جداگانه) ---------------------------
async def hads_kalame_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if await check_ban_status(update, context): return
    
    chat_id = update.effective_chat.id
    if chat_id in active_games['hangman']:
        await query.answer("یک بازی حدس کلمه فعال است.", show_alert=True)
        return
        
    word = random.choice(WORD_LIST)
    active_games['hangman'][chat_id] = {"word": word, "display": ["_"] * len(word), "guessed_letters": set(), "players": {}}
    game = active_games['hangman'][chat_id]
    text = f"🕵️‍♂️ **حدس کلمه (رقابتی) شروع شد!**\n\nهر کاربر {INITIAL_LIVES} جان دارد.\n\n|نکته*:|به صورت تک حرفی حدس بزنید.مثال:(م)*\n\nکلمه: `{' '.join(game['display'])}`"
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_letter_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, user = update.effective_chat.id, update.effective_user
    if chat_id not in active_games['hangman']: return
    if await check_ban_status(update, context): return

    guess = update.message.text.strip()
    game = active_games['hangman'][chat_id]
    
    if user.id not in game['players']: game['players'][user.id] = INITIAL_LIVES
    if game['players'][user.id] == 0: 
        await update.message.reply_text(f"{user.mention_html()}، شما تمام جان‌های خود را از دست داده‌اید!", parse_mode=ParseMode.HTML)
        return

    # ##### تغییر کلیدی: اطلاع‌رسانی برای حرف تکراری #####
    if guess in game['guessed_letters']:
        await update.message.reply_text("این حرف قبلاً گفته شده!", quote=True)
        return

    game['guessed_letters'].add(guess)
    if guess in game['word']:
        for i, letter in enumerate(game['word']):
            if letter == guess: game['display'][i] = letter
        if "_" not in game['display']:
            await update.message.reply_text(f"✅ **{user.mention_html()}** برنده شد! کلمه صحیح `{game['word']}` بود.", parse_mode=ParseMode.HTML, reply_markup=None)
            del active_games['hangman'][chat_id]
        else:
            await update.message.reply_text(f"`{' '.join(game['display'])}`", parse_mode=ParseMode.MARKDOWN)
    else:
        game['players'][user.id] -= 1
        lives_left = game['players'][user.id]
        if lives_left > 0:
            await update.message.reply_text(f"اشتباه بود {user.mention_html()}! شما **{lives_left}** جان دیگر دارید.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"{user.mention_html()} تمام جان‌های خود را از دست داد و از بازی حذف شد.", parse_mode=ParseMode.HTML)
            # چک کردن اینکه آیا همه بازیکنان حذف شده‌اند یا خیر
            active_players_lives = [lives for uid, lives in game['players'].items() if lives > 0]
            if not active_players_lives:
                await update.message.reply_text(f"☠️ همه باختید! کلمه صحیح `{game['word']}` بود.", parse_mode=ParseMode.MARKDOWN)
                del active_games['hangman'][chat_id]

# --------------------------- GAME: TYPE SPEED ---------------------------
def create_typing_image(text: str) -> io.BytesIO:
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    try:
        font = ImageFont.truetype("Vazir.ttf", 24)
    except IOError:
        logger.warning("Vazir.ttf font not found. Falling back to default.")
        font = ImageFont.load_default()
    
    dummy_img, draw = Image.new('RGB', (1, 1)), ImageDraw.Draw(Image.new('RGB', (1, 1)))
    _, _, w, h = draw.textbbox((0, 0), bidi_text, font=font)
    img = Image.new('RGB', (w + 40, h + 40), color=(255, 255, 255))
    ImageDraw.Draw(img).text((20, 20), bidi_text, fill=(0, 0, 0), font=font)
    bio = io.BytesIO()
    bio.name = 'image.jpeg'
    img.save(bio, 'JPEG')
    bio.seek(0)
    return bio

async def type_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if await check_ban_status(update, context): return
    
    chat_id = update.effective_chat.id
    if chat_id in active_games['typing']: 
        await query.answer("یک بازی تایپ سرعتی فعال است.", show_alert=True)
        return
        
    sentence = random.choice(TYPING_SENTENCES)
    active_games['typing'][chat_id] = {"sentence": sentence, "start_time": datetime.now()}
    
    await query.edit_message_text("بازی تایپ سرعتی ۳... ۲... ۱...")
    image_file = create_typing_image(sentence)
    await context.bot.send_photo(chat_id=chat_id, photo=image_file, caption="سریع تایپ کنید!")

async def handle_typing_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games['typing']: return
    if await check_ban_status(update, context): return
    
    game = active_games['typing'][chat_id]
    user_input = update.message.text.strip()
    
    if user_input == game['sentence']:
        duration = (datetime.now() - game['start_time']).total_seconds()
        user = update.effective_user
        await update.message.reply_text(f"🏆 {user.mention_html()} برنده شد!\nزمان: **{duration:.2f}** ثانیه", parse_mode=ParseMode.HTML)
        del active_games['typing'][chat_id]

# --------------------------- GAME: GHARCH & ETERAF ---------------------------
# (منطق این بازی‌ها عمدتاً بدون تغییر است، فقط نحوه شروع آنها از پنل اضافه شده)
async def gharch_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if await check_ban_status(update, context): return ConversationHandler.END

    if not await is_group_admin(update.effective_user.id, update.effective_chat.id, context):
        await query.answer("❌ فقط ادمین‌های گروه می‌توانند این بازی را شروع کنند.", show_alert=True)
        return ConversationHandler.END
    
    context.chat_data['starter_admin_id'] = update.effective_user.id
    await query.edit_message_text(
        "🍄 **شروع بازی قارچ**\n\n"
        "لطفاً یوزرنیم گاد بازی را ارسال کنید (مثال: @GodUsername).\nبرای لغو /cancel را ارسال کنید."
    )
    context.chat_data['gharch_setup_message_id'] = query.message.message_id
    return ASKING_GOD_USERNAME

async def receive_god_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    god_username = update.message.text.strip()
    if not god_username.startswith('@'):
        await update.message.reply_text("فرمت اشتباه است. لطفاً یوزرنیم را با @ ارسال کنید.", quote=True)
        return ASKING_GOD_USERNAME

    context.chat_data['god_username'] = god_username
    starter_admin_id = context.chat_data['starter_admin_id']
    setup_message_id = context.chat_data.get('gharch_setup_message_id')

    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete admin's username message: {e}")

    if not setup_message_id:
        await context.bot.send_message(update.effective_chat.id, "خطایی در یافتن پیام اصلی رخ داد. لطفاً بازی را با /cancel لغو و مجدداً شروع کنید.")
        return ConversationHandler.END

    keyboard = [[
        InlineKeyboardButton("✅ تایید می‌کنم", callback_data=f"gharch_confirm_god_{starter_admin_id}")
    ]]
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=setup_message_id,
        text=(
            f"{god_username} عزیز،\n"
            f"شما به عنوان گاد بازی قارچ انتخاب شدید. لطفاً برای شروع بازی، این مسئولیت را تایید کنید.\n\n"
            f"⚠️ **نکته:** برای دریافت گزارش‌ها، باید ربات را استارت کرده باشید."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRMING_GOD

async def confirm_god(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """گاد بازی را تایید کرده و بازی رسماً شروع می‌شود."""
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    
    god_username_from_admin = context.chat_data.get('god_username', '').lower().lstrip('@')

    if not user.username or user.username.lower() != god_username_from_admin:
        await query.answer("این درخواست برای شما نیست، یا یوزرنیم تلگرام شما تنظیم نشده است.", show_alert=True)
        return CONFIRMING_GOD

    await query.answer("شما به عنوان گاد تایید شدید!")

    try:
        god_id = user.id
        god_username_display = f"@{user.username}"
        active_gharch_games[chat_id] = {'god_id': god_id, 'god_username': god_username_display}

        bot_username = (await context.bot.get_me()).username
        game_message_text = (
            "**بازی قارچ 🍄 شروع شد!**\n\n"
            "روی دکمه زیر کلیک کن و حرف دلت رو بنویس تا به صورت ناشناس در گروه ظاهر بشه!\n\n"
            f"*(فقط گاد بازی، {god_username_display}، از هویت ارسال‌کننده مطلع خواهد شد.)*"
        )
        keyboard = [[InlineKeyboardButton("🍄 ارسال پیام ناشناس", url=f"https://t.me/{bot_username}?start=gharch_{chat_id}")]]
        
        await query.edit_message_text(
            text=game_message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.pin_chat_message(chat_id, query.message.message_id)
            active_gharch_games[chat_id]['pinned_message_id'] = query.message.message_id
        except Exception as pin_error:
            logger.warning(f"Could not pin message in group {chat_id}. Reason: {pin_error}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ بازی با موفقیت شروع شد. ادمین‌های عزیز، لطفاً این پیام را پین کنید.",
                reply_to_message_id=query.message.message_id
            )

    except Exception as e:
        error_message = f"🚫 **خطای ناشناخته!**\n\nربات در ساخت بازی با یک خطای غیرمنتظره مواجه شد: `{e}`"
        await context.bot.send_message(chat_id=chat_id, text=error_message, parse_mode=ParseMode.MARKDOWN)
        logger.error(f"CRITICAL ERROR in confirm_god: {e}")
        return ConversationHandler.END

    return ConversationHandler.END

async def cancel_gharch_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """لغو فرآیند ساخت بازی قارچ."""
    await update.message.reply_text("فرآیند ساخت بازی قارچ لغو شد.")
    await rsgame_command(update, context)
    return ConversationHandler.END

async def eteraf_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if await check_ban_status(update, context): return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    if not await is_group_admin(user.id, chat_id, context):
        await query.answer("❌ شما اجازه استفاده از این دستور را ندارید.", show_alert=True)
        return
    
    data = query.data.split('_')
    eteraf_type = data[2] 

    if eteraf_type == "default":
        starter_text = "یک موضوع اعتراف جدید شروع شد. برای ارسال اعتراف ناشناس، از دکمه زیر استفاده کنید."
        bot_username = (await context.bot.get_me()).username
        try:
            starter_message = await context.bot.send_message(chat_id, starter_text)
            keyboard = [[InlineKeyboardButton("🤫 ارسال اعتراف", url=f"https://t.me/{bot_username}?start=eteraf_{chat_id}_{starter_message.message_id}")]]
            await starter_message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            await query.message.delete() 
        except Exception as e:
            logger.error(f"Error in eteraf_command: {e}")
        return

    elif eteraf_type == "custom":
        # ##### تغییر جدید: ذخیره آیدی پیام برای حذف در آینده #####
        context.chat_data['eteraf_prompt_message_id'] = query.message.message_id
        await query.edit_message_text("لطفاً متن دلخواه خود را برای شروع اعتراف ارسال کنید.\nبرای لغو /cancel را ارسال کنید.")
        return ENTERING_ETERAF_TEXT

async def receive_eteraf_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_text = update.message.text
    chat_id = update.effective_chat.id
    bot_username = (await context.bot.get_me()).username
    
    try:
        # ربات پیام جدید اعتراف را با دکمه ارسال می‌کند
        starter_message = await context.bot.send_message(chat_id, custom_text)
        keyboard = [[InlineKeyboardButton("🤫 ارسال اعتراف", url=f"https://t.me/{bot_username}?start=eteraf_{chat_id}_{starter_message.message_id}")]]
        await starter_message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in eteraf_command (custom): {e}")
        await update.message.reply_text(f"خطایی در ارسال پیام رخ داد: {e}")
    finally:
        # پیام قبلی ربات ("لطفا متن خود را ارسال کنید") حذف می‌شود
        prompt_message_id = context.chat_data.pop('eteraf_prompt_message_id', None)
        try:
            if prompt_message_id:
                await context.bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)
            
            # ##### تغییر اصلی: خط زیر حذف شد #####
            # await update.message.delete() # -> این خط دیگر وجود ندارد و پیام شما باقی می‌ماند.

        except Exception:
            pass
            
        return ConversationHandler.END

async def handle_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    if 'anon_target_chat' not in user_data:
        return await update.message.reply_text("لطفاً ابتدا از طریق دکمه‌ای که در گروه قرار دارد، فرآیند را شروع کنید.")
    
    target_info = user_data['anon_target_chat']
    target_chat_id = target_info['id']
    game_type = target_info['type']
    message_text = update.message.text

    try:
        if game_type == "gharch":
            if target_chat_id in active_gharch_games:
                sender = update.effective_user
                god_info = active_gharch_games[target_chat_id]
                god_id = god_info['god_id']

                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=f"#پیام_ناشناس 🍄\n\n{message_text}"
                )
                await update.message.reply_text("✅ پیام شما با موفقیت به صورت ناشناس در گروه ارسال شد.")

                report_text = (
                    f"📝 **گزارش پیام ناشناس جدید**\n\n"
                    f"👤 **ارسال کننده:**\n"
                    f"- نام: {sender.mention_html()}\n"
                    f"- یوزرنیم: @{sender.username}\n"
                    f"- آیدی: `{sender.id}`\n\n"
                    f"📜 **متن پیام:**\n"
                    f"{message_text}"
                )
                await context.bot.send_message(chat_id=god_id, text=report_text, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("این بازی قارچ دیگر فعال نیست یا منقضی شده است.")

        elif game_type == "eteraf":
            reply_to_id = target_info.get('reply_to')
            header = "#اعتراف_ناشناس 🤫"
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=f"{header}\n\n{message_text}",
                reply_to_message_id=reply_to_id
            )
            await update.message.reply_text("✅ اعتراف شما با موفقیت به صورت ناشناس در گروه ارسال شد.")
        
        else:
            await update.message.reply_text("نوع بازی ناشناس مشخص نیست.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ ارسال پیام با خطا مواجه شد: {e}")
        logger.error(f"Error in handle_anonymous_message for game {game_type}: {e}")
    finally:
        if 'anon_target_chat' in context.user_data:
            del context.user_data['anon_target_chat']


# =================================================================
# ================= OWNER & CORE COMMANDS (بدون تغییر) =============
# =================================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if await check_ban_status(update, context): return

    # --- بخش ۱: مدیریت لینک‌های ورودی (Deep Linking) ---
    if context.args:
        try:
            payload = context.args[0]
            parts = payload.split('_')
            game_type, target_chat_id = parts[0], int(parts[1])

            if game_type == "gharch":
                if target_chat_id in active_gharch_games:
                    god_username = active_gharch_games[target_chat_id]['god_username']
                    context.user_data['anon_target_chat'] = {'id': target_chat_id, 'type': game_type}
                    prompt = f"پیام خود را برای ارسال ناشناس بنویسید...\n\nتوجه: فقط گاد بازی ({god_username}) هویت شما را خواهد دید."
                    await update.message.reply_text(prompt)
                    return
                else:
                    await update.message.reply_text("این بازی قارچ دیگر فعال نیست."); return
            
            elif game_type == "eteraf":
                context.user_data['anon_target_chat'] = {'id': target_chat_id, 'type': game_type}
                if len(parts) > 2:
                    context.user_data['anon_target_chat']['reply_to'] = int(parts[2])
                prompt = "اعتراف خود را بنویسید تا به صورت ناشناس در گروه ارسال شود..."
                await update.message.reply_text(prompt)
                return

        except (ValueError, IndexError):
            pass # اگر payload معتبر نبود، به بخش استارت معمولی می‌رود

    # --- بخش ۲: منطق استارت معمولی ---
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur: 
            cur.execute("INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING;", (user.id, user.first_name, user.username))
            conn.commit()
    
    # اینجا عضویت اجباری برای استارت معمولی چک نمی‌شود، فقط در بازی‌های خاص
    
    # --- بخش ۳: ارسال پیام خوشامدگویی (سفارشی یا پیش‌فرض) ---
    keyboard = [
        [InlineKeyboardButton("➕ افزودن ربات به گروه", url=f"https://t.me/{(await context.bot.get_me()).username}?startgroup=true")],
        #[InlineKeyboardButton("🎮 پنل بازی‌ها", callback_data="rsgame_cat_main_pv")], # دکمه پنل در PV
        [InlineKeyboardButton("👤 ارتباط با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    custom_welcome_sent = False
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id, chat_id FROM start_message WHERE id = 1;")
                start_msg_data = cur.fetchone()
                if start_msg_data:
                    message_id, from_chat_id = start_msg_data
                    await context.bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id, reply_markup=reply_markup)
                    custom_welcome_sent = True
        except Exception as e:
            logger.error(f"Could not send custom start message in PV: {e}")
        finally:
            conn.close()

    if not custom_welcome_sent:
        await update.message.reply_text("سلام به راینوبازی خوش آمدید.\nبرای شروع بازی‌ها از دکمه زیر استفاده کنید.", reply_markup=reply_markup)
    
    report_text = f"✅ کاربر جدید: {user.mention_html()} (ID: `{user.id}`)"
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(chat_id=owner_id, text=report_text, parse_mode=ParseMode.HTML)
        except:
            pass
            
async def rsgame_pv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هنگامی که کاربر در PV روی دکمه پنل کلیک می‌کند"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("این پنل فقط در گروه‌ها کار می‌کند. لطفاً ربات را به یک گروه اضافه کرده و دستور /rsgame را ارسال کنید.")


# بقیه دستورات ادمین (stats, fwdusers, ...) بدون تغییر باقی می‌مانند
# ...
async def set_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not update.message.reply_to_message: return await update.message.reply_text("روی یک پیام ریپلای کنید.")
    msg = update.message.reply_to_message
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur: cur.execute("INSERT INTO start_message (id, message_id, chat_id) VALUES (1, %s, %s) ON CONFLICT (id) DO UPDATE SET message_id = EXCLUDED.message_id, chat_id = EXCLUDED.chat_id;", (msg.message_id, msg.chat_id)); conn.commit()
        conn.close()
        await update.message.reply_text("✅ پیام خوشامدگویی تنظیم شد.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;"); user_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM groups;"); group_count = cur.fetchone()[0]
            cur.execute("SELECT SUM(member_count) FROM groups;"); total_members = cur.fetchone()[0] or 0
        stats = f"📊 **آمار ربات**\n\n👤 کاربران: {user_count}\n👥 گروه‌ها: {group_count}\n👨‍👩‍👧‍👦 مجموع اعضا: {total_members}"
        await update.message.reply_text(stats, parse_mode=ParseMode.MARKDOWN)
        conn.close()
        
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    if not await is_owner(update.effective_user.id): return
    if not update.message.reply_to_message: return await update.message.reply_text("روی یک پیام ریپلای کنید.")
    conn, table, column = get_db_connection(), "users" if target == "users" else "groups", "user_id" if target == "users" else "group_id"
    if not conn: return
    with conn.cursor() as cur: cur.execute(f"SELECT {column} FROM {table};"); targets = cur.fetchall()
    conn.close()
    if not targets: return await update.message.reply_text("هدفی یافت نشد.")
    
    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"⏳ در حال ارسال به {len(targets)} {target}...")
    for (target_id,) in targets:
        try:
            await context.bot.forward_message(chat_id=target_id, from_chat_id=update.message.reply_to_message.chat.id, message_id=update.message.reply_to_message.message_id)
            sent += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast failed for {target_id}: {e}")
    await status_msg.edit_text(f"🏁 ارسال تمام شد.\n\n✅ موفق: {sent}\n❌ ناموفق: {failed}")

async def fwdusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await broadcast_command(update, context, "users")
async def fwdgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await broadcast_command(update, context, "groups")

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /leave <group_id>")
    try:
        group_id = int(context.args[0])
        await context.bot.leave_chat(group_id)
        await update.message.reply_text(f"✅ با موفقیت از گروه `{group_id}` خارج شدم.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")

async def grouplist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT group_id, title, member_count FROM groups;")
            groups = cur.fetchall()
        conn.close()
        if not groups: return await update.message.reply_text("ربات در هیچ گروهی عضو نیست.")
        message = "📜 **لیست گروه‌ها:**\n\n"
        for i, (group_id, title, member_count) in enumerate(groups, 1):
            message += f"{i}. **{title}**\n   - ID: `{group_id}`\n   - اعضا: {member_count}\n\n"
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /join <group_id>")
    try:
        group_id = int(context.args[0])
        link = await context.bot.create_chat_invite_link(group_id, member_limit=30)
        await update.message.reply_text(f"لینک ورود شما:\n{link.invite_link}")
    except Exception as e:
        await update.message.reply_text(f"خطا در ساخت لینک (شاید ربات ادمین نباشد): {e}")

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /ban_user <user_id>")
    try:
        user_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur: cur.execute("INSERT INTO banned_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_id,))
            conn.commit(); conn.close()
            await update.message.reply_text(f"کاربر `{user_id}` با موفقیت مسدود شد.", parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("آیدی نامعتبر است.")

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده: /unban_user <user_id>")
    try:
        user_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur: cur.execute("DELETE FROM banned_users WHERE user_id = %s;", (user_id,))
            conn.commit(); conn.close()
            await update.message.reply_text(f"کاربر `{user_id}` با موفقیت از مسدودیت خارج شد.", parse_mode=ParseMode.MARKDOWN)
    except: await update.message.reply_text("آیدی نامعتبر است.")

async def ban_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bans a group from using the bot."""
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده صحیح: /ban_group <group_id>")
    
    try:
        group_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO banned_groups (group_id) VALUES (%s) ON CONFLICT DO NOTHING;", (group_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"گروه `{group_id}` با موفقیت مسدود شد.", parse_mode=ParseMode.MARKDOWN)
            
            # Bot leaves the group after banning it
            try:
                await context.bot.leave_chat(group_id)
            except Exception as e:
                logger.warning(f"Could not leave the banned group {group_id}: {e}")

    except (ValueError, IndexError):
        await update.message.reply_text("لطفا یک آیدی عددی معتبر برای گروه وارد کنید.")

async def unban_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unbans a group."""
    if not await is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("استفاده صحیح: /unban_group <group_id>")

    try:
        group_id = int(context.args[0])
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM banned_groups WHERE group_id = %s;", (group_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"گروه `{group_id}` با موفقیت از مسدودیت خارج شد.", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text("لطفا یک آیدی عددی معتبر برای گروه وارد کنید.")
# -----------------
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = update.chat_member
    if not result: return

    chat = result.chat
    user = result.from_user # کاربری که ربات را اضافه کرده
    
    # مطمئن می‌شویم که تغییر وضعیت مربوط به ربات ماست
    if result.new_chat_member.user.id != context.bot.id:
        return

    # --- وقتی ربات به گروه اضافه می‌شود ---
    if result.new_chat_member.status == 'member' and result.old_chat_member.status != 'member':
        conn = get_db_connection()
        if not conn: return
        
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM groups;"); group_count = cur.fetchone()[0]
            
            if group_count >= GROUP_INSTALL_LIMIT:
                await chat.send_message(f"⚠️ ظرفیت نصب این ربات تکمیل شده است! لطفاً با پشتیبانی (@{SUPPORT_USERNAME}) تماس بگیرید.")
                await context.bot.leave_chat(chat.id)
                for owner_id in OWNER_IDS:
                    await context.bot.send_message(owner_id, f"🔔 هشدار: سقف نصب ({GROUP_INSTALL_LIMIT}) تکمیل شد. ربات از گروه `{chat.title}` خارج شد.", parse_mode=ParseMode.MARKDOWN)
                conn.close()
                return
        except Exception as e:
            logger.error(f"Could not check group install limit: {e}")

        member_count = await chat.get_member_count()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO groups (group_id, title, member_count) VALUES (%s, %s, %s) ON CONFLICT (group_id) DO UPDATE SET title = EXCLUDED.title, member_count = EXCLUDED.member_count;", (chat.id, chat.title, member_count))
            conn.commit()

        # ارسال پیام خوشامدگویی همراه با دکمه پنل
        keyboard = [[InlineKeyboardButton("🎮 نمایش پنل بازی‌ها", callback_data="rsgame_cat_main")]]
        await chat.send_message("سلام! 👋 من با موفقیت نصب شدم.\nبرای شروع از دستور /rsgame یا دکمه زیر استفاده کنید.", reply_markup=InlineKeyboardMarkup(keyboard))
        
        conn.close()
        
        report = f"➕ **ربات به گروه جدید اضافه شد:**\n\n🌐 نام: {chat.title}\n🆔: `{chat.id}`\n👥 اعضا: {member_count}\n\n👤 توسط: {user.mention_html()} (ID: `{user.id}`)"
        for owner_id in OWNER_IDS:
            try: await context.bot.send_message(owner_id, report, parse_mode=ParseMode.HTML)
            except: pass

    # --- وقتی ربات از گروه حذف می‌شود ---
    elif result.new_chat_member.status == 'left':
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM groups WHERE group_id = %s;", (chat.id,))
                conn.commit()
            conn.close()
        report = f"❌ **ربات از گروه زیر اخراج شد:**\n\n🌐 نام: {chat.title}\n🆔: `{chat.id}`"
        for owner_id in OWNER_IDS:
            try: await context.bot.send_message(owner_id, report, parse_mode=ParseMode.MARKDOWN)
            except: pass

async def stop_games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دستور لغو تمام بازی‌های فعال در یک گروه توسط ادمین.
    این دستور بازی‌های ناشناس (قارچ) را لغو نمی‌کند.
    """
    chat = update.effective_chat
    user = update.effective_user

    # ۱. این دستور فقط در گروه‌ها کار می‌کند
    if chat.type == 'private':
        await update.message.reply_text("این دستور فقط در گروه‌ها قابل استفاده است.")
        return

    # ۲. فقط ادمین‌ها می‌توانند از این دستور استفاده کنند
    if not await is_group_admin(user.id, chat.id, context):
        await update.message.reply_text("❌ شما اجازه استفاده از این دستور را ندارید. این دستور مخصوص مدیران است.")
        return
        
    chat_id = chat.id
    canceled_count = 0

    # ۳. لیست بازی‌هایی که باید لغو شوند
    # بازی قارچ (gharch) در این لیست نیست
    games_to_cancel = ['hangman', 'typing', 'guess_number']

    for game_key in games_to_cancel:
        # بررسی می‌کند آیا بازی از این نوع در این گروه فعال است یا خیر
        if chat_id in active_games.get(game_key, {}):
            # حذف تمام بازی‌های فعال آن نوع از گروه فعلی
            del active_games[game_key][chat_id]
            canceled_count += 1
            
    # ۴. ارسال پیام نتیجه به ادمین
    if canceled_count > 0:
        await update.message.reply_text(f"✅ با موفقیت {canceled_count} نوع بازی فعال لغو شد.")
    else:
        await update.message.reply_text("هیچ بازی فعالی برای لغو کردن در این گروه وجود نداشت.")

async def text_help_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """با دریافت کلمه 'راهنما'، پیام راهنمای بازی‌ها را ارسال می‌کند."""
    
    help_text = """
🎮 **راهنمای بازی‌های ربات** 🎮

برای شروع هر بازی، از پنل اصلی با دستور /rsgame استفاده کنید. در ادامه معرفی کوتاهی از هر بازی را مشاهده می‌کنید:

---
**🏆 بازی‌های کارتی و گروهی**

- **حکم (۲ و ۴ نفره):** بازی کارتی محبوب و استراتژیک.

- **دوز (دو نفره):** بازی کلاسیک XO یا Tic-Tac-Toe.

---
**✍️ بازی‌های تایپی و سرعتی**

- **حدس کلمه:** یک کلمه مخفی می‌شود و شما باید با حدس حروف، آن را پیدا کنید.

- **تایپ سرعتی:** یک جمله نمایش داده می‌شود و اولین کسی که آن را درست تایپ کند، برنده است.

- **حدس عدد (ویژه ادمین):** ادمین محدوده‌ای را مشخص می‌کند و ربات عددی را انتخاب می‌کند تا بقیه حدس بزنند.

---
**🤫 بازی‌های ناشناس (ویژه ادمین)**

- **اعتراف:** ادمین یک موضوع اعتراف ایجاد می‌کند و اعضا به صورت ناشناس به آن پاسخ می‌دهند.

- **قارچ:** ادمین یک "گاد" برای بازی تعیین می‌کند و اعضا به صورت ناشناس پیام ارسال می‌کنند. هویت ارسال‌کننده فقط برای گاد فاش می‌شود.

---
برای لغو تمام بازی‌های فعال در گروه (فقط توسط ادمین): /stop
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    سرعت پاسخ‌دهی (latency) ربات را محاسبه کرده و فقط برای مالک ربات ارسال می‌کند.
    """
    # ۱. زمان شروع را قبل از ارسال پیام ثبت می‌کنیم
    start_time = time.time()
    
    # ۲. یک پیام اولیه ارسال می‌کنیم تا بتوانیم آن را ویرایش کنیم
    message = await update.message.reply_text("...")
    
    # ۳. زمان پایان را پس از ارسال پیام ثبت می‌کنیم
    end_time = time.time()
    
    # ۴. اختلاف زمان را محاسبه و به میلی‌ثانیه تبدیل می‌کنیم
    latency_s = end_time - start_time
    
    # ۵. پیام اولیه را با نتیجه نهایی ویرایش می‌کنیم
    await message.edit_text(f"راینو گیم آنلاین است!\n\n⚡️پاسخگویی: {latency_s:.4f} ثانیه")

# =================================================================
# ======================== MAIN FUNCTION ==========================
# =================================================================
def main() -> None:
    """Start the bot."""
    setup_database()
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    
    # --- Conversation Handlers (باید اولویت بالاتری داشته باشند) ---
    gharch_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gharch_start_callback, pattern=r'^gharch_start_')],
        states={
            ASKING_GOD_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_god_username)],
            CONFIRMING_GOD: [CallbackQueryHandler(confirm_god, pattern=r'^gharch_confirm_god_')],
        },
        fallbacks=[CommandHandler('cancel', cancel_gharch_conv)],
        per_user=False, per_chat=True,
    )
    
    guess_number_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(hads_addad_start_callback, pattern=r'^hads_addad_start_')],
        states={
            SELECTING_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_range)],
            GUESSING: [MessageHandler(filters.Regex(r'^[\d۰-۹]+$'), handle_guess_conversation)],
        },
        fallbacks=[CommandHandler('cancel', cancel_game_conversation)],
        per_user=False, per_chat=True
    )

    eteraf_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(eteraf_start_callback, pattern=r'^eteraf_start_custom_')],
        states={
            ENTERING_ETERAF_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_eteraf_text)]
        },
        fallbacks=[CommandHandler('cancel', cancel_game_conversation)], # از همان تابع لغو مشترک استفاده می‌کند
        per_user=True, per_chat=False # این مکالمه باید برای هر کاربر جدا باشد
    )

    application.add_handler(gharch_conv)
    application.add_handler(guess_number_conv)
    application.add_handler(eteraf_conv)

    # --- Command Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("rsgame", rsgame_command))

    application.add_handler(CommandHandler("stop", stop_games_command))
    
    # دستورات مالک ربات
    application.add_handler(CommandHandler("setstart", set_start_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("stats", stats_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("fwdusers", fwdusers_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("fwdgroups", fwdgroups_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("leave", leave_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("grouplist", grouplist_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("join", join_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("ban_user", ban_user_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("unban_user", unban_user_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("ban_group", ban_group_command, filters=filters.User(OWNER_IDS)))
    application.add_handler(CommandHandler("unban_group", unban_group_command, filters=filters.User(OWNER_IDS)))

    application.add_handler(CallbackQueryHandler(rsgame_check_join_callback, pattern=r'^rsgame_check_join$'))

    # پنل اصلی
    application.add_handler(CallbackQueryHandler(rsgame_callback_handler, pattern=r'^rsgame_cat_'))
    application.add_handler(CallbackQueryHandler(rsgame_pv_callback, pattern=r'^rsgame_cat_main_pv$'))
    # شروع بازی‌ها از پنل
    # FIX: الگوها را اصلاح کنید
    application.add_handler(CallbackQueryHandler(rsgame_close_callback, pattern=r'^rsgame_close_'))
    application.add_handler(CallbackQueryHandler(hads_kalame_start_callback, pattern=r'^hads_kalame_start_'))
    application.add_handler(CallbackQueryHandler(type_start_callback, pattern=r'^type_start_'))
    application.add_handler(CallbackQueryHandler(eteraf_start_callback, pattern=r'^eteraf_start_default_'))
    # مدیریت داخلی بازی‌ها
    application.add_handler(CallbackQueryHandler(hokm_callback, pattern=r'^hokm_'))
    application.add_handler(CallbackQueryHandler(dooz_callback, pattern=r'^dooz_'))

    application.add_handler(MessageHandler(filters.Regex(r'^راهنما$') & filters.ChatType.GROUPS, text_help_trigger))

    application.add_handler(MessageHandler(filters.Regex(r'^پینگ$') & filters.User(OWNER_IDS), ping_command))
    
    # --- Message Handlers (باید اولویت کمتری داشته باشند) ---
    application.add_handler(MessageHandler(filters.Regex(r'^[آ-ی]$') & filters.ChatType.GROUPS, handle_letter_guess))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_anonymous_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_typing_attempt))
    
    # --- سایر Handler ها ---
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    
    logger.info("Bot is starting with the new refactored logic...")
    application.run_polling()

if __name__ == "__main__":
    main()
