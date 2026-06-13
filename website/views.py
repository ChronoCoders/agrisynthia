from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _

BLOG_POSTS = [
    {
        "slug": "ndvi-nedir-nasil-okunur",
        "title": _("NDVI Nedir ve Tarla Sağlığını Nasıl Anlatır?"),
        "excerpt": _("Normalized Difference Vegetation Index: uydu görüntülerinden bitki canlılığını ölçen bu indeks, hasattan önce verimi tahmin etmek için neden kritik öneme sahip?"),
        "category": _("NDVI & Uydu"),
        "cat_slug": "ndvi",
        "date": _("8 Mayıs 2026"),
        "read_time": 6,
        "icon": "fa-satellite",
        "image": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=800&q=80&fit=crop",
        "content": _("""
<p>NDVI (Normalize Edilmiş Bitki Örtüsü İndeksi), kırmızı ve yakın kızılötesi ışık bantlarının farkından hesaplanan bir sayısal değerdir. Değer -1 ile +1 arasında değişir; 0,5 ve üzeri sağlıklı ve yoğun bitkisel aktiviteyi, 0,3'ün altı ise stres ya da seyrek örtüyü gösterir.</p>
<h2>Neden önemli?</h2>
<p>Bir tarladaki klorofil miktarı düşmeye başladığında (kuraklık, hastalık veya besin eksikliği nedeniyle), bu değişim insan gözüyle görünür hale gelmeden çok önce kızılötesi bantta kendini belli eder. Agrisynthia, Sentinel-2 uydusunun her 5 günde bir çektiği görüntüleri işleyerek bu değişimi otomatik tespit eder.</p>
<h2>NDVI değerleri nasıl yorumlanır?</h2>
<ul>
<li><strong>0,6 ve üzeri:</strong> Yoğun, sağlıklı bitki örtüsü, ideal durum</li>
<li><strong>0,4-0,6:</strong> Normal sezon seyri, dikkatli izleme yeterli</li>
<li><strong>0,3-0,4:</strong> Hafif stres, sulama veya gübre kontrolü önerilir</li>
<li><strong>0,3 altı:</strong> Ciddi stres veya hasar. Acil saha müdahalesi gerekebilir</li>
</ul>
<blockquote>Agrisynthia'da belirlediğiniz eşiğin altına düştüğünde otomatik e-posta uyarısı gönderilir. Sahaya gitmeden önce neye bakacağınızı bilirsiniz.</blockquote>
<h2>Uydu NDVI ile drone NDVI farkı</h2>
<p>Sentinel-2 uydusu 10 metre/piksel çözünürlükle tarlayı genel olarak değerlendirir. Drone ise santimetre çözünürlüğünde çalışır ve tarla içindeki leke bazlı farklılıkları gösterir. İkisini birlikte kullanmak en kapsamlı tabloyu sunar.</p>
"""),
    },
    {
        "slug": "drone-ortofoto-nasil-olusturulur",
        "title": _("Drone ile Tarla Haritası Çıkarma: 4 Adımda Anlattık"),
        "excerpt": _("Drone'unuzla çektiğiniz fotoğraflar, tarlanızın detaylı bir sağlık haritasına dönüşebilir. Yazılım bilgisi gerekmez. Sadece fotoğraf yükleyin."),
        "category": _("Drone"),
        "cat_slug": "drone",
        "date": _("2 Mayıs 2026"),
        "read_time": 8,
        "icon": "fa-helicopter",
        "image": "https://images.unsplash.com/photo-1657093114835-031e7cf9520c?w=800&q=80&fit=crop",
        "content": _("""
<p>Drone ile çekilen fotoğraflar tek başına bir anlam taşımaz. Asıl değer, bu fotoğrafların birleştirilerek tarlanızın yukarıdan eksiksiz bir görüntüsünün oluşturulmasıyla ortaya çıkar. Agrisynthia bu işlemi sizin için tamamen otomatik yapar. Hiçbir teknik bilgi gerekmez.</p>
<h2>1. Drone'u doğru uçurun</h2>
<p>En iyi sonuç için drone'u sabit yükseklikte, tarla üzerinde ızgara çizerek uçurun. Fotoğrafların birbiriyle örtüşmesi önemlidir. Modern drone uygulamalarının çoğu bu uçuş planını otomatik oluşturabilir.</p>
<h2>2. Fotoğrafları yükleyin</h2>
<p>Agrisynthia'da "Drone Projeleri" bölümünden yeni proje oluşturun. Tüm fotoğrafları sürükleyip bırakın. Sistem konum bilgilerini fotoğraflardan otomatik okur, sizin bir şey yapmanıza gerek kalmaz.</p>
<h2>3. Bekleyin: sistem çalışıyor</h2>
<p>Yükleme tamamlanınca işleme otomatik başlar. Fotoğraf sayısına göre 10-40 dakika sürer. Sayfayı kapatabilirsiniz, iş bitince e-posta ile haber verilir.</p>
<h2>4. Sağlık haritanızı inceleyin</h2>
<p>Harita hazır olduğunda tarlanızın hangi bölümlerinin sağlıklı, hangilerinin stresli olduğunu renk renk görebilirsiniz. Sorunlu alanları yakınlaştırın, haritayı indirin ya da ekibinizle paylaşın.</p>
<blockquote>İpucu: Sabah erken veya öğleden sonra geç saatlerde çekilen fotoğraflar, sert gölge olmadığı için çok daha net sonuç verir.</blockquote>
"""),
    },
    {
        "slug": "meyve-tespitinde-yapay-zeka",
        "title": _("Yapay Zeka ile Meyve Sayımı: Hasattan Önce Ne Kadar Ürün Var?"),
        "excerpt": _("Elle saymak hem zaman alır hem de yanıltır. Telefonunuzla çektiğiniz birkaç fotoğraf, bahçenizdeki toplam meyveyi dakikalar içinde hesaplayabilir."),
        "category": _("Teknoloji"),
        "cat_slug": "tech",
        "date": _("25 Nisan 2026"),
        "read_time": 7,
        "icon": "fa-microchip",
        "image": "https://images.unsplash.com/photo-1507598641400-ec3536ba81bc?w=800&q=80&fit=crop",
        "content": _("""
<p>Yüzlerce ağaçlık bir bahçede meyve saymak, hem zaman hem de emek ister. Geleneksel yöntemlerle yapılan tahminlerin hata payı %20-40 arasında değişir. Bu, fazla işçi çağırmak ya da alıcıya yanlış fiyat vermek anlamına gelebilir. Agrisynthia'nın yapay zeka destekli sayım özelliği bu hata payını %6'nın altına indirir.</p>
<h2>Nasıl çalışır?</h2>
<p>Bahçenizden birkaç fotoğraf çekin ve Agrisynthia'ya yükleyin. Sistem her fotoğraftaki meyveleri tek tek tanır, işaretler ve sayar. Ağaç başına düşen ortalama meyve sayısını, tahmini toplam ağırlığı ve beklenen tonajı dakikalar içinde görürsünüz.</p>
<h2>Hangi meyveler destekleniyor?</h2>
<ul>
<li>Mandalina ve narenciye</li>
<li>Elma (kırmızı ve yeşil çeşitler)</li>
<li>Armut</li>
<li>Şeftali</li>
<li>Nar</li>
</ul>
<h2>İyi sonuç için ne yapmalısınız?</h2>
<ul>
<li>Güneşli bir günde, gölge az olduğunda çekin</li>
<li>Ağaca 2-5 metre mesafeden fotoğraflayın</li>
<li>Her fotoğrafda en az 20-30 meyve görünür olsun</li>
<li>Telefonunuzun fotoğraf kalitesi yeterliyse özel ekipman gerekmez</li>
</ul>
<blockquote>Sistem size sadece sayıyı değil, ne kadar emin olduğunu da gösterir. Belirsiz görüntülerde sizi uyarır, o kareleri yeniden çekmenizi önerir.</blockquote>
"""),
    },
    {
        "slug": "verim-tahmini-agronomi-modeli",
        "title": _("Verim Tahmini İçin Kullandığımız Agronomi Modeli"),
        "excerpt": _("Tespit verileri + NDVI + ağaç yaşı faktörü: Agrisynthia'nın verim tahmin modelinin arkasındaki bilimsel yaklaşımı açıkladık."),
        "category": _("Agronomi"),
        "cat_slug": "agronomy",
        "date": _("18 Nisan 2026"),
        "read_time": 9,
        "icon": "fa-chart-line",
        "image": "https://images.unsplash.com/photo-1500651230702-0e2d8a49d4ad?w=800&q=80&fit=crop",
        "content": _("""
<p>Agrisynthia'nın verim tahmin motoru, üç bağımsız veri kaynağını birleştiren çok etkenli bir agronomi modelidir: görüntü bazlı meyve yoğunluğu, uydu NDVI verisi ve ağaç biyolojik parametreleri.</p>
<h2>Model bileşenleri</h2>
<h3>1. Görüntü bazlı meyve yoğunluğu</h3>
<p>YOLOv7 tespitinden elde edilen meyve sayısı, görüntünün kapsadığı alan ve ağaç sayısına bölünerek ağaç başına meyve yoğunluğu hesaplanır.</p>
<h3>2. NDVI stres faktörü</h3>
<p>Son 6 haftanın ortalama NDVI değeri, türe özel optimum NDVI ile karşılaştırılır. Stres altındaki bitkiler daha az ve daha hafif meyve üretir; model bu ilişkiyi üstel bir düzeltme faktörüyle yansıtır.</p>
<h3>3. Ağaç yaşı düzeltmesi</h3>
<p>Meyve ağaçları tam verim yaşına (4-6 yıl) ulaşmadan düşük verimlidir. Model, genç ağaçlar için orantılı bir düzeltme uygular.</p>
<blockquote>Modelimizi bir öngörü aracı olarak, sahada agronomunuzun deneyimiyle birleştirerek kullanın. Veri ile sezgi birlikte en iyi kararı verir.</blockquote>
"""),
    },
    {
        "slug": "turk-tariminda-dijital-donusum",
        "title": _("Türk Tarımında Dijital Dönüşüm: Neredeyiz, Nereye Gidiyoruz?"),
        "excerpt": _("Türkiye'nin tarım sektörü, dünya genelinde dijitalleşme dalgasını yakalayabildi mi? Güncel veriler ve fırsatlar üzerine bir analiz."),
        "category": _("Agronomi"),
        "cat_slug": "agronomy",
        "date": _("10 Nisan 2026"),
        "read_time": 10,
        "icon": "fa-seedling",
        "image": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=800&q=80&fit=crop",
        "content": _("""
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
"""),
    },
    {
        "slug": "sentinel-2-ucretsiz-uydu-verisi",
        "title": _("Tarlanız Her 5 Günde Bir Uydudan İzleniyor. Bunu Biliyor muydunuz?"),
        "excerpt": _("Avrupa'nın tarım uydusu Türkiye'yi düzenli olarak tarıyor ve bu veriler herkese ücretsiz açık. Agrisynthia bu veriyi sizin için anlamlı hale getiriyor."),
        "category": _("NDVI & Uydu"),
        "cat_slug": "ndvi",
        "date": _("3 Nisan 2026"),
        "read_time": 7,
        "icon": "fa-globe",
        "image": "https://images.unsplash.com/photo-1536183922588-166604504d5e?w=800&q=80&fit=crop",
        "content": _("""
<p>Avrupa Uzay Ajansı'nın işlettiği bir uydu, her 5 günde bir Türkiye'nin tamamını görüntüler. Bu görüntüler herkese açık ve ücretsizdir. Ama ham haliyle yorumlanmaları uzmanlık gerektirir. Agrisynthia bu yorumu sizin için otomatik yapar ve tarlanızın sağlık durumunu sade bir renkli haritaya dönüştürür.</p>
<h2>Bu uydu tarlanız için ne yapabilir?</h2>
<p>Uydu, bitkilerinizin yaydığı ışığı ölçer. Sağlıklı bitkiler bu ölçümde canlı ve yoğun görünürken, stres altındaki ya da kuruyan bitkiler soluk görünür. Bu sayede tarlada gezip görmeden önce sorunlu alanları tespit etmek mümkün olur.</p>
<h2>Ne zaman işe yarar, ne zaman yaramaz?</h2>
<ul>
<li><strong>İşe yarar:</strong> Büyük alanlarda genel sağlık takibi, mevsimsel karşılaştırma, erken uyarı</li>
<li><strong>Yetersiz kalır:</strong> Tek bir ağacı veya küçük bir lekeyi incelemek için yetersiz, bunun için drone gerekir</li>
<li><strong>Bulutlu havalarda:</strong> Sistem bulut geçen günleri atlar, bir sonraki açık günü bekler</li>
</ul>
<h2>Agrisynthia olmadan kullanabilir misiniz?</h2>
<p>Teorik olarak evet, ama pratik olarak çok zordur. Ham uydu verisi indirmek, işlemek ve yorumlamak saatler alır ve teknik bilgi gerektirir. Agrisynthia tüm bu adımları arka planda halleder; siz sadece haritanıza bakarsınız.</p>
<blockquote>Tarlanız 5 günde bir uydudan geçiyor. Bu bilgiyi değerlendirmek artık sadece büyük çiftliklerin ayrıcalığı değil.</blockquote>
"""),
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
        _("14 gün ücretsiz deneme"),
        _("SSL güvenlik"),
        _("KVKK uyumlu veri saklama"),
        _("Türkçe destek"),
        _("İstediğiniz zaman iptal"),
    ]
    return render(request, "website/pricing.html", {"included_items": included_items})


def about(request):
    techs = [
        {"icon": "fa-satellite", "name": _("Uydu Görüntüleme"), "desc": _("Her 5 günde güncellenen uydu verileriyle tarlanızı sürekli takip edin.")},
        {"icon": "fa-robot", "name": _("Yapay Zeka Tespiti"), "desc": _("Görüntülerden meyve ve mahsulü %94+ doğrulukla otomatik sayar.")},
        {"icon": "fa-helicopter", "name": _("Drone Haritalama"), "desc": _("Drone görüntülerinizi yükleyin, platformumuz detaylı alan haritasını oluşturur.")},
        {"icon": "fa-bolt", "name": _("Anlık İşleme"), "desc": _("Yüklediğiniz veriler arka planda işlenir; sonuçlar hazır olunca sizi bildirir.")},
        {"icon": "fa-leaf", "name": _("NDVI Analizi"), "desc": _("Bitkilerinizin sağlığını renkli haritalarla görün, sorunlu alanları anında fark edin.")},
        {"icon": "fa-map-location-dot", "name": _("Etkileşimli Harita"), "desc": _("Tüm tarlalarınızı tek ekranda izleyin, alanlara tıklayarak detay görün.")},
        {"icon": "fa-shield-halved", "name": _("Güvenli Depolama"), "desc": _("Verileriniz Türkiye'de güvenli sunucularda saklanır, başkasıyla paylaşılmaz.")},
        {"icon": "fa-file-alt", "name": _("Otomatik Raporlar"), "desc": _("PDF ve Excel raporları belirlediğiniz sıklıkta e-posta kutunuza iletilir.")},
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


@require_POST
def newsletter_subscribe(request):
    from .models import NewsletterSubscriber
    email = request.POST.get("email", "").strip().lower()
    if not email:
        return JsonResponse({"ok": False, "error": "E-posta adresi gerekli."}, status=400)
    _, created = NewsletterSubscriber.objects.get_or_create(email=email)
    return JsonResponse({"ok": True, "created": created})


@require_POST
def chat_lead(request):
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False}, status=400)
    from .models import ChatLead
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not (full_name and email and phone):
        return JsonResponse({"ok": False, "error": _("Tüm alanlar zorunludur.")}, status=400)
    ChatLead.objects.create(full_name=full_name, email=email, phone=phone)
    return JsonResponse({"ok": True})


_CHATBOT_SYSTEM = """Sen Agrisynthia'nın yardımcı asistanısın. Agrisynthia, Türkiye'deki çiftçiler ve tarım işletmeleri için yapay zeka destekli bir tarım platformudur.

Platform özellikleri:
- Uydu NDVI analizi (Sentinel-2 verileriyle bitki sağlığı izleme)
- Drone görüntü işleme ve ortofoto oluşturma
- YOLOv7 tabanlı yapay zeka meyve/mahsul tespiti
- Verim tahmini (NDVI + ağaç yaşı + tespit verileri)
- Proje ve tarla yönetimi
- PDF/Excel raporlama ve e-posta uyarıları

Fiyat planları:
- Bireysel: 890 TL/ay (3 tarla, aylık 50 görüntü, haftalık NDVI)
- Kooperatif: 2.490 TL/ay (25 tarla, sınırsız görüntü, günlük NDVI) - En Popüler
- Kurumsal: Teklif alın (sınırsız, API erişimi, SLA, öncelikli destek)
- Tüm planlar 14 gün ücretsiz deneme ile başlar, kredi kartı gerekmez.

İletişim: info@agrisynthia.com
Web: agrisynthia.com

Sık sorulan sorular ve doğru cevaplar:

NDVI & Uydu:
S: NDVI değerim 0.3 çıktı, bu iyi mi?
C: 0.3 zayıf bitki örtüsüne işaret eder. 0.5 ve üzeri sağlıklı, 0.7 ve üzeri mükemmel kabul edilir. Sulama veya gübreleme ihtiyacı olabilir.

S: NDVI ne sıklıkla güncelleniyor?
C: Bireysel planda haftada bir, Kooperatif planda günlük, Kurumsal planda gerçek zamanlı güncellenir.

S: Bulutlu havalarda NDVI doğru çıkar mı?
C: Bulut örtüsü yüksekse Sentinel-2 uydusu o geçişi atlar ve bir sonraki net görüntüyü bekler. Sistem otomatik olarak en düşük bulut oranına sahip sahneyi seçer.

Drone & Görüntü:
S: Drone görüntüsünü nasıl yüklerim?
C: Dashboard'dan Projeler → Drone Analizi menüsüne girin, yeni proje oluşturun ve JPG/TIFF formatındaki görüntülerinizi sürükleyip bırakın.

S: Hangi drone modelleri destekleniyor?
C: Herhangi bir drone ile çekilmiş JPEG veya TIFF görüntüleri kabul edilir. DJI, Parrot ve diğer tüm markalar çalışır; markaya özel bir kısıt yoktur.

S: Ortofoto oluşturma ne kadar sürer?
C: Görüntü sayısına ve çözünürlüğe bağlı olarak 10 dakika ile 1 saat arasında değişir. İşlem tamamlandığında e-posta ile bildirim alırsınız.

Meyve Tespiti & Verim:
S: Sistem hangi meyveleri tanıyabilir?
C: Şu anda mandalina, portakal, limon, elma, nar ve zeytin desteklenmektedir. Yeni türler sürekli eklenmektedir.

S: Verim tahmini ne kadar doğru?
C: Model, NDVI, ağaç yaşı ve görüntüden tespit edilen meyve sayısını birleştirerek tahmin yapar. Ortalama sapma %15-25 arasındadır; gerçek hasat hava koşulları ve bakıma göre farklılık gösterebilir.

S: Meyve tespiti için kaç görüntü gerekir?
C: En az 1 görüntü yeterlidir ancak birden fazla açıdan çekilmiş görüntüler doğruluğu artırır.

Hesap & Plan:
S: Ücretsiz deneme süresi bittikten sonra ne olur?
C: 14 günlük deneme sonunda size bir hatırlatma e-postası gönderilir. Ücretli plana geçmezseniz hesabınız salt okunur moda geçer, verileriniz silinmez.

S: Plan değiştirmek istiyorum, ne yapmalıyım?
C: Hesap Ayarları → Abonelik bölümünden istediğiniz plana geçebilirsiniz. Ücret farkı gün bazında hesaplanır.

S: Birden fazla kullanıcı aynı hesabı kullanabilir mi?
C: Kooperatif ve Kurumsal planlarda çoklu kullanıcı desteği mevcuttur. Bireysel plan tek kullanıcı içindir.

Teknik & Destek:
S: Verilerim güvende mi?
C: Tüm veriler Türkiye'deki sunucularda şifreli olarak saklanır. KVKK kapsamında kişisel verileriniz üçüncü taraflarla paylaşılmaz.

S: Mobil cihazdan kullanabilir miyim?
C: Evet, platform tüm modern tarayıcılarda çalışır. Ayrıca mobil uyumlu arayüzü sayesinde telefon ve tabletten de rahatça kullanılabilir.

S: Teknik bir sorunum var, nasıl destek alabilirim?
C: info@agrisynthia.com adresine e-posta gönderebilirsiniz. Kooperatif planında 24 saat, Kurumsal planda SLA garantili öncelikli destek sunulmaktadır.

Kurallar:
- Sadece Agrisynthia ve tarım ile ilgili sorulara cevap ver.
- Kısa, net ve samimi cevaplar ver. Madde listesi kullanabilirsin.
- Fiyat veya teknik destek için kullanıcıyı info@agrisynthia.com adresine yönlendir.
- Türkçe konuş; kullanıcı başka dilde yazarsa o dilde yanıtla.
"""


@require_POST
def chatbot_chat(request):
    import json
    import os
    import anthropic
    from django_ratelimit.core import is_ratelimited

    if request.user.is_authenticated:
        limited = is_ratelimited(
            request,
            group="chatbot_auth",
            key="user",
            rate="30/m",
            method="POST",
            increment=True,
        )
    else:
        limited = is_ratelimited(
            request,
            group="chatbot_anon",
            key="ip",
            rate="10/m",
            method="POST",
            increment=True,
        )

    if limited:
        return JsonResponse(
            {"ok": False, "error": _("Çok fazla istek. Lütfen bir dakika bekleyin.")},
            status=429,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "Gecersiz istek."}, status=400)

    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not user_message:
        return JsonResponse({"ok": False, "error": "Mesaj bos olamaz."}, status=400)

    messages = []
    for turn in history[-10:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_CHATBOT_SYSTEM,
            messages=messages,
        )
        reply = response.content[0].text
        return JsonResponse({"ok": True, "reply": reply})
    except anthropic.AuthenticationError:
        return JsonResponse({"ok": False, "error": "API anahtari yapilandirilmamis."}, status=500)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
