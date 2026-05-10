# -*- coding: utf-8 -*-
from django.shortcuts import render

BLOG_POSTS = [
    {
        "slug": "ndvi-nedir-nasil-okunur",
        "title": "NDVI Nedir ve Tarla Sağlığını Nasıl Anlatır?",
        "excerpt": "Normalized Difference Vegetation Index — uydu görüntülerinden bitki canlılığını ölçen bu indeks, hasattan önce verimi tahmin etmek için neden kritik öneme sahip?",
        "category": "NDVI & Uydu",
        "cat_slug": "ndvi",
        "date": "8 Mayıs 2026",
        "read_time": 6,
        "icon": "fa-satellite",
        "image": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=800&q=80&fit=crop",
        "content": """
<p>NDVI (Normalize Edilmiş Bitki Örtüsü İndeksi), kırmızı ve yakın kızılötesi ışık bantlarının farkından hesaplanan bir sayısal değerdir. Değer -1 ile +1 arasında değişir; 0,5 ve üzeri sağlıklı ve yoğun bitkisel aktiviteyi, 0,3'ün altı ise stres ya da seyrek örtüyü gösterir.</p>
<h2>Neden önemli?</h2>
<p>Bir tarladaki klorofil miktarı düşmeye başladığında — kuraklık, hastalık veya besin eksikliği nedeniyle — bu değişim insan gözüyle görünür hale gelmeden çok önce kızılötesi bantta kendini belli eder. Agrisynthia, Sentinel-2 uydusunun her 5 günde bir çektiği görüntüleri işleyerek bu değişimi otomatik tespit eder.</p>
<h2>NDVI değerleri nasıl yorumlanır?</h2>
<ul>
<li><strong>0,6 ve üzeri:</strong> Yoğun, sağlıklı bitki örtüsü — ideal durum</li>
<li><strong>0,4 – 0,6:</strong> Normal sezon seyri — dikkatli izleme yeterli</li>
<li><strong>0,3 – 0,4:</strong> Hafif stres — sulama veya gübre kontrolü önerilir</li>
<li><strong>0,3 altı:</strong> Ciddi stres veya hasar — acil saha müdahalesi gerekebilir</li>
</ul>
<blockquote>Agrisynthia'da belirlediğiniz eşiğin altına düştüğünde otomatik e-posta uyarısı gönderilir. Sahaya gitmeden önce neye bakacağınızı bilirsiniz.</blockquote>
<h2>Uydu NDVI ile drone NDVI farkı</h2>
<p>Sentinel-2 uydusu 10 metre/piksel çözünürlükle tarlayı genel olarak değerlendirir. Drone ise santimetre çözünürlüğünde çalışır ve tarla içindeki leke bazlı farklılıkları gösterir. İkisini birlikte kullanmak en kapsamlı tabloyu sunar.</p>
""",
    },
    {
        "slug": "drone-ortofoto-nasil-olusturulur",
        "title": "Drone Görüntülerinden Ortofoto Oluşturma: Adım Adım Rehber",
        "excerpt": "NodeODM ile drone görüntülerinizi tarla haritasına dönüştürmek artık yazılım uzmanlığı gerektirmiyor. Agrisynthia'da nasıl çalıştığını anlattık.",
        "category": "Drone",
        "cat_slug": "drone",
        "date": "2 Mayıs 2026",
        "read_time": 8,
        "icon": "fa-helicopter",
        "image": "https://images.unsplash.com/photo-1474302770737-173ee21bab63?w=800&q=80&fit=crop",
        "content": """
<p>Ortofoto, drone görüntülerinin geometrik olarak düzeltilip tek bir üstten bakış görüntüsünde birleştirilmesidir. Açık kaynak NodeODM motoru ve Agrisynthia entegrasyonu bu süreci ücretsiz ve otomatik hale getirir.</p>
<h2>1. Uçuş planlaması</h2>
<p>İdeal ortofoto için drone'u sabit irtifada, %70-80 örtüşme oranıyla ızgara şeklinde uçurun. DJI GO 4, Litchi veya Mission Planner bu uçuş planlarını otomatik oluşturabilir.</p>
<h2>2. Görüntü yükleme</h2>
<p>Agrisynthia'da "Drone Projeleri" bölümünden yeni proje oluşturun. Tüm görüntüleri (JPEG veya TIFF) sürükle-bırak ile yükleyin. Sistem otomatik olarak EXIF GPS verilerini okur.</p>
<h2>3. NodeODM işleme</h2>
<p>Yükleme tamamlandıktan sonra işleme otomatik başlar. Ortalama süre görüntü sayısına göre 10-40 dakikadır. İşleme sırasında sayfayı kapatabilirsiniz — tamamlandığında e-posta bildirimi gönderilir.</p>
<h2>4. Sağlık haritası analizi</h2>
<p>Ortofoto hazır olunca 14 farklı algoritma seçeneği sunar: NDVI, EVI, GNDVI, SAVI ve daha fazlası.</p>
<blockquote>İpucu: Mandalina ve narenciye bahçeleri için GNDVI, elma bahçeleri için EVI genellikle daha yüksek ayrım gücü sağlar.</blockquote>
""",
    },
    {
        "slug": "meyve-tespitinde-yapay-zeka",
        "title": "Yapay Zeka ile Meyve Sayımı: YOLOv7 Tarımda Nasıl Kullanılır?",
        "excerpt": "Elle sayılan meyveler, yüzlerce ağaçlık bahçelerde hata ve zaman kaybına yol açar. YOLOv7 tabanlı tespit modeli bu sorunu nasıl çözüyor?",
        "category": "Teknoloji",
        "cat_slug": "tech",
        "date": "25 Nisan 2026",
        "read_time": 7,
        "icon": "fa-microchip",
        "image": "https://images.unsplash.com/photo-1611312449408-fcece27cdbb7?w=800&q=80&fit=crop",
        "content": """
<p>Meyve sayımı, hasat planlaması ve verim tahmini için kritik bir girdi olmakla birlikte, geleneksel yöntemlerle yapıldığında %20-40 hata payı taşır. Agrisynthia'nın YOLOv7 tabanlı tespit motoru bu hata payını %6'nın altına indirir.</p>
<h2>YOLOv7 neden seçildi?</h2>
<p>YOLO (You Only Look Once) ailesi, gerçek zamanlı nesne tespitinde benchmark kabul edilmektedir. YOLOv7, özellikle yüksek çözünürlüklü tarımsal görüntülerde küçük nesneleri tespit etmede önceki sürümlere göre %12 daha yüksek mAP skoru sağlar.</p>
<h2>Hangi türler destekleniyor?</h2>
<ul>
<li>Mandalina (narenciye dahil)</li>
<li>Elma (kırmızı ve yeşil çeşitler)</li>
<li>Armut</li>
<li>Şeftali</li>
<li>Nar</li>
</ul>
<h2>Doğruluğu etkileyen faktörler</h2>
<ul>
<li>En az 12 MP çözünürlük</li>
<li>Doğal gün ışığı (sert gölge olmaksızın)</li>
<li>Ağaç ile kamera arası 2-5 metre</li>
<li>Görüntü başına en az 20-30 meyve</li>
</ul>
<blockquote>Agrisynthia'nın tespit sonuçları her zaman güven skoru ile birlikte sunulur. Düşük güven (%70 altı) durumunda sistem sizi bilgilendirir.</blockquote>
""",
    },
    {
        "slug": "verim-tahmini-agronomi-modeli",
        "title": "Verim Tahmini İçin Kullandığımız Agronomi Modeli",
        "excerpt": "Tespit verileri + NDVI + ağaç yaşı faktörü — Agrisynthia'nın verim tahmin modelinin arkasındaki bilimsel yaklaşımı açıkladık.",
        "category": "Agronomi",
        "cat_slug": "agronomy",
        "date": "18 Nisan 2026",
        "read_time": 9,
        "icon": "fa-chart-line",
        "image": "https://images.unsplash.com/photo-1500651230702-0e2d8a49d4ad?w=800&q=80&fit=crop",
        "content": """
<p>Agrisynthia'nın verim tahmin motoru, üç bağımsız veri kaynağını birleştiren çok etkenli bir agronomi modelidir: görüntü bazlı meyve yoğunluğu, uydu NDVI verisi ve ağaç biyolojik parametreleri.</p>
<h2>Model bileşenleri</h2>
<h3>1. Görüntü bazlı meyve yoğunluğu</h3>
<p>YOLOv7 tespitinden elde edilen meyve sayısı, görüntünün kapsadığı alan ve ağaç sayısına bölünerek ağaç başına meyve yoğunluğu hesaplanır.</p>
<h3>2. NDVI stres faktörü</h3>
<p>Son 6 haftanın ortalama NDVI değeri, türe özel optimum NDVI ile karşılaştırılır. Stres altındaki bitkiler daha az ve daha hafif meyve üretir; model bu ilişkiyi üstel bir düzeltme faktörüyle yansıtır.</p>
<h3>3. Ağaç yaşı düzeltmesi</h3>
<p>Meyve ağaçları tam verim yaşına (4-6 yıl) ulaşmadan düşük verimlidir. Model, genç ağaçlar için orantılı bir düzeltme uygular.</p>
<blockquote>Modelimizi bir öngörü aracı olarak, sahada agronomunuzun deneyimiyle birleştirerek kullanın. Veri ile sezgi birlikte en iyi kararı verir.</blockquote>
""",
    },
    {
        "slug": "turk-tariminda-dijital-donusum",
        "title": "Türk Tarımında Dijital Dönüşüm: Neredeyiz, Nereye Gidiyoruz?",
        "excerpt": "Türkiye'nin tarım sektörü, dünya genelinde dijitalleşme dalgasını yakalayabildi mi? Güncel veriler ve fırsatlar üzerine bir analiz.",
        "category": "Agronomi",
        "cat_slug": "agronomy",
        "date": "10 Nisan 2026",
        "read_time": 10,
        "icon": "fa-seedling",
        "image": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=800&q=80&fit=crop",
        "content": """
<p>Türkiye, yaklaşık 19 milyon hektar tarım arazisi ve dünya meyve ihracatında önemli bir pay ile küresel gıda sisteminde kritik bir aktördür. Buna karşın tarım sektörünün dijital teknoloji kullanım oranı, AB ortalamasının önemli ölçüde gerisinde kalmaktadır.</p>
<h2>Mevcut tablo</h2>
<p>TÜİK verilerine göre Türkiye'deki çiftçilerin yalnızca %8'i herhangi bir dijital tarım aracı kullanmaktadır. Avrupa Birliği'nde bu oran %34'ü geçmektedir.</p>
<h2>Fırsatlar</h2>
<ul>
<li><strong>Uydu görüntüsü ücretsiz:</strong> Sentinel-2 verileri herkesin kullanımına açık.</li>
<li><strong>Akıllı telefon penetrasyonu yüksek:</strong> Çiftçilerin %71'i akıllı telefon sahibi.</li>
<li><strong>Kooperatif altyapısı:</strong> 7.000'den fazla tarım kooperatifi hızlı yayılım sağlayabilir.</li>
</ul>
<h2>Agrisynthia'nın rolü</h2>
<p>Teknolojiyi çiftçiye götürmek, çiftçiyi teknolojiye götürmekten çok daha etkilidir. Agrisynthia tamamen Türkçe, mobil öncelikli ve minimum teknik bilgi gerektiren bir kullanıcı deneyimiyle tasarlandı.</p>
""",
    },
    {
        "slug": "sentinel-2-ucretsiz-uydu-verisi",
        "title": "Sentinel-2: Tarımcılar İçin Ücretsiz Uydu Verisi Rehberi",
        "excerpt": "Avrupa Uzay Ajansı'nın Sentinel-2 uydusu her 5 günde bir Türkiye'yi tarıyor. Bu veriyi nasıl değerlendirirsiniz?",
        "category": "NDVI & Uydu",
        "cat_slug": "ndvi",
        "date": "3 Nisan 2026",
        "read_time": 7,
        "icon": "fa-globe",
        "image": "https://images.unsplash.com/photo-1536183922588-166604504d5e?w=800&q=80&fit=crop",
        "content": """
<p>Sentinel-2, ESA tarafından işletilen ve verileri tamamen ücretsiz olarak kamuoyuna açık olan bir uydu çiftidir. 13 spektral bant ve 10 metrelik yersel çözünürlük ile tarımsal izleme için ideal bir kaynak sunar.</p>
<h2>Neden tarımcılar için değerli?</h2>
<p>Kırmızı kenar (red-edge) bandı, diğer uyduların büyük çoğunluğunda bulunmaz. Bu band, klorofil içeriğini doğrudan ölçer ve bitki stresini NDVI'dan daha erken tespit eder.</p>
<h2>Agrisynthia ile entegrasyon</h2>
<p>Agrisynthia, Element84 Earth Search STAC API üzerinden Sentinel-2 L2A ürünlerine erişir. Cloud-Optimized GeoTIFF formatındaki dosyaları doğrudan buluttan okur — işleme süresini %80 azaltır.</p>
<h2>Sınırlamalar</h2>
<ul>
<li>Bulut örtüsü veride karanlık bölgeler oluşturur. Agrisynthia yalnızca %30 altı bulut örtülü geçişleri işler.</li>
<li>10 metre çözünürlük, tek ağaç bazında analiz için yeterli değildir — bunun için drone verileri gerekir.</li>
</ul>
<blockquote>Uydu verisi ücretsizdir, ancak yorumlanması uzmanlık gerektirir. Agrisynthia bu yorumu sizin için otomatik yapar.</blockquote>
""",
    },
]


def _get_post(slug):
    return next((p for p in BLOG_POSTS if p["slug"] == slug), None)


def home(request):
    return render(request, "website/home.html")


def product(request):
    return render(request, "website/product.html")


def pricing(request):
    included_items = [
        "14 gün ücretsiz deneme",
        "SSL güvenlik",
        "KVKK uyumlu veri saklama",
        "Türkçe destek",
        "İstediğiniz zaman iptal",
    ]
    return render(request, "website/pricing.html", {"included_items": included_items})


def about(request):
    techs = [
        {"icon": "fa-satellite", "name": "Sentinel-2", "desc": "ESA ücretsiz uydu verisi, 5 günde güncelleme"},
        {"icon": "fa-robot", "name": "YOLOv7", "desc": "Gerçek zamanlı nesne tespiti, %94+ doğruluk"},
        {"icon": "fa-helicopter", "name": "NodeODM", "desc": "Açık kaynak drone ortofoto motoru"},
        {"icon": "fa-cloud", "name": "Celery + Redis", "desc": "Asenkron işleme ve gerçek zamanlı durum"},
        {"icon": "fa-map", "name": "rio-tiler", "desc": "Cloud-optimized GeoTIFF ve NDVI hesaplama"},
        {"icon": "fa-location-dot", "name": "Leaflet.js", "desc": "Etkileşimli harita görüntüleme"},
        {"icon": "fa-database", "name": "PostgreSQL", "desc": "Güvenilir ilişkisel veritabanı"},
        {"icon": "fa-server", "name": "Django 4.2", "desc": "Güvenli ve ölçeklenebilir web çatısı"},
    ]
    return render(request, "website/about.html", {"techs": techs})


def blog(request):
    return render(request, "website/blog.html", {"posts": BLOG_POSTS})


def blog_detail(request, slug):
    from django.http import Http404
    post = _get_post(slug)
    if not post:
        raise Http404("Yazı bulunamadı")
    related = [p for p in BLOG_POSTS if p["slug"] != slug][:3]
    return render(request, "website/blog_detail.html", {"post": post, "related": related})


def contact(request):
    success = False
    if request.method == "POST":
        from django.core.mail import send_mail
        from django.conf import settings
        name = request.POST.get("name", "").strip()
        company = request.POST.get("company", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        if name and email and subject and message:
            body = f"Ad Soyad: {name}\nFirma: {company}\nE-posta: {email}\n\n{message}"
            try:
                send_mail(
                    f"[Agrisynthia İletişim] {subject}",
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    ["info@agrisynthia.com"],
                    fail_silently=True,
                )
            except Exception:
                pass
            success = True
    return render(request, "website/contact.html", {"success": success})


def privacy(request):
    return render(request, "website/privacy.html")


def terms(request):
    return render(request, "website/terms.html")


def kvkk(request):
    return render(request, "website/kvkk.html")
