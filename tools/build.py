"""Static site builder for readyfix.ca.

Page content lives in src/pages/. Each file starts with a JSON front-matter
comment, followed by the markup that goes inside <main>. This script wraps it
in the shared layout (head, SEO tags, JSON-LD, header, footer) and writes the
finished HTML to the same relative path at the repo root, which is what
Vercel serves. It also regenerates sitemap.xml.

    python tools/build.py

Front matter keys:
    title, description  required
    nav                 key of the nav item to mark current ("home", "services", a service slug, an area slug, "about", "pricing")
    crumbs              [[label, url], ...] after Home; last item's url may be null
    service             service slug -> adds Service schema
    area                area slug -> adds area Service schema
    robots              defaults to "index, follow, max-image-preview:large"
    sitemap             priority (0.1-1.0) to include in sitemap.xml; omit to leave out
    og_image            absolute path such as /img/og-image.jpg
    minimal             true for bare pages (404, thanks): no JSON-LD / OG tags

Partials, written as <!--@name {json args}--> inside page content:
    page_hero, contact, cta, services_grid, related_services, areas, testimonials, process, trust_bar
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "pages"

BASE = "https://www.readyfix.ca"
PHONE = "647-699-4607"
TEL = "+16476994607"
EMAIL = "braydon@readyfix.ca"
GA_ID = "G-S58K8S2G0D"
FORM_ACTION = "https://formspree.io/f/xrbowkdd"
BIZ_ID = f"{BASE}/#business"
HOMESTARS = "https://www.homestars.com/profile/ready-fix-handyman-services"
INSTAGRAM = "https://www.instagram.com/readyfixhandyman"

# slug, short label (nav), card title, card blurb, icon, schema name
SERVICES = [
    ("drywall-repair-toronto", "Drywall repair", "Drywall repair &amp; patching",
     "Holes, cracks, water damage and ceiling patches, texture-matched and paint-ready.", "drywall", "Drywall repair"),
    ("punch-list", "Punch lists", "Punch lists &amp; inspection fixes",
     "Closing, move-in and inspection items cleared in one organized visit.", "list", "Punch list repairs"),
    ("cabinet-repair-toronto", "Cabinet repair", "Cabinet &amp; hardware repair",
     "Sagging doors, loose hinges, drawer slides and soft-close upgrades.", "cabinet", "Cabinet repair"),
    ("doors-trim", "Doors &amp; trim", "Door &amp; trim repair",
     "Sticking doors, latches, baseboards and casing fixed and caulked.", "door", "Door and trim repair"),
    ("mount-artwork-tv", "TV &amp; art mounting", "TV &amp; artwork mounting",
     "TVs, mirrors, shelves and gallery walls mounted level with tidy cables.", "tv", "TV and artwork mounting"),
    ("lock-replacement", "Lock replacement", "Lock replacement",
     "Deadbolts and handlesets swapped, strikes aligned, latching checked.", "lock", "Lock replacement"),
    ("curtain-rod-installation", "Curtain rods", "Curtain rod installation",
     "Rods and brackets anchored into studs or concrete, perfectly level.", "curtain", "Curtain rod installation"),
    ("small-jobs", "Small jobs", "Small handyman jobs",
     "The odd jobs list: adjustments, touch-ups and quick fixes in one trip.", "wrench", "Small handyman jobs"),
]
SERVICE_BY_SLUG = {s[0]: s for s in SERVICES}

# slug, display name, schema place name
AREAS = [
    ("downtown-toronto", "Downtown Toronto", "Toronto"),
    ("east-york", "East York", "East York"),
    ("north-york", "North York", "North York"),
    ("etobicoke", "Etobicoke", "Etobicoke"),
    ("scarborough", "Scarborough", "Scarborough"),
    ("york", "York", "York"),
    ("mississauga", "Mississauga", "Mississauga"),
    ("markham", "Markham", "Markham"),
]
AREA_BY_SLUG = {a[0]: a for a in AREAS}

TESTIMONIALS = [
    ("ReadyFix patched a massive ceiling hole and matched the texture in one visit. Clean, respectful, on-budget.",
     "Jenna", "Junction Triangle"),
    ("They handled my pre-listing touch-ups and even coordinated with the painter. Sold the condo in 48 hours.",
     "Daniel", "Liberty Village"),
    ("Smart recommendations, clear pricing, and fast communication. ReadyFix is now on our property manager list.",
     "Rachel", "East York"),
]


def esc(s):
    """Escape for attribute values; input may already contain entities."""
    return html.escape(html.unescape(str(s)), quote=True)


def plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def icon(name, cls="icon"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"></use></svg>'


# ------------------------------------------------------------------ icons

ICONS = {
    "drywall": '<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 9h18M3 15h18M9 4v5M15 9v6M9 15v5"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3.5 6 1.5 1.5L7.5 5M3.5 12l1.5 1.5L7.5 11M3.5 18l1.5 1.5L7.5 17"/>',
    "cabinet": '<rect x="3" y="3" width="18" height="18" rx="1.5"/><path d="M12 3v18M9 10v4M15 10v4"/>',
    "door": '<path d="M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17M3 21h18"/><circle cx="15" cy="12" r="1"/>',
    "tv": '<rect x="2" y="4" width="20" height="13" rx="1.5"/><path d="M8 21h8M12 17v4"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
    "curtain": '<path d="M2 4h20M5 4v16c2-2 3-5 3-8s-1-6-3-8M19 4v16c-2-2-3-5-3-8s1-6 3-8"/>',
    "wrench": '<path d="M14.5 6.5a4 4 0 0 0 5 5L21 13l-8 8-3-3 8-8-1.5-1.5a4 4 0 0 1-5-5L13 2l1.5 4.5z"/><path d="m3 21 6-6"/>',
    "phone": '<path d="M6.6 3h3l1.5 4.5-2 1.5a12 12 0 0 0 5.9 5.9l1.5-2L21 14.4v3A2.6 2.6 0 0 1 18.4 20 15.4 15.4 0 0 1 4 5.6 2.6 2.6 0 0 1 6.6 3z"/>',
    "message": '<path d="M4 5h16v11H9l-5 4z"/>',
    "check": '<path d="m4 12.5 5 5L20 6.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "shield": '<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "camera": '<path d="M4 7h3l2-3h6l2 3h3v13H4z"/><circle cx="12" cy="13" r="3.5"/>',
    "broom": '<path d="M14 3 9.5 11M7 11h7l2 10H5z"/><path d="M8.5 15v6M11.5 15v6"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "menu": '<path d="M3 6h18M3 12h18M3 18h18"/>',
}


def icon_sprite():
    filled = {"star"}
    symbols = "".join(
        f'<symbol id="i-{k}" viewBox="0 0 24 24" fill="{"currentColor" if k in filled else "none"}" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{v}</symbol>'
        for k, v in ICONS.items()
    )
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true">{symbols}</svg>'


# ------------------------------------------------------------------ partials

def picture(name, widths, alt, sizes="100vw", cls="", eager=False, width=None, height=None):
    """<picture> for images produced by tools/optimize_images.py."""
    srcset = lambda ext: ", ".join(f"/img/{name}-{w}.{ext} {w}w" for w in widths)
    attrs = 'fetchpriority="high" decoding="async"' if eager else 'loading="lazy" decoding="async"'
    dims = f' width="{width}" height="{height}"' if width else ""
    return (f'<picture class="{cls}"><source type="image/webp" srcset="{srcset("webp")}" sizes="{sizes}">'
            f'<img src="/img/{name}-{widths[-1]}.jpg" srcset="{srcset("jpg")}" sizes="{sizes}" alt="{esc(alt)}"{dims} {attrs}></picture>')


def breadcrumbs(page):
    items = [("Home", "/")] + [tuple(c) for c in page.get("crumbs", [])]
    lis = []
    for i, (label, url) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li aria-current="page">{label}</li>')
        else:
            lis.append(f'<li><a href="{url}">{label}</a></li>')
    return f'<nav class="breadcrumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'


def p_page_hero(page, title, lead="", eyebrow="", image="circular-saw", widths=(800, 1400), cta=True):
    actions = ""
    if cta:
        actions = f"""
      <div class="hero__actions">
        <a class="btn btn--primary btn--lg" data-track="cta:call" href="tel:{TEL}">{icon("phone")}Call {PHONE}</a>
        <a class="btn btn--light btn--lg" href="#contact">Get a free quote</a>
      </div>"""
    eyebrow_html = f'<p class="eyebrow eyebrow--light">{eyebrow}</p>' if eyebrow else ""
    lead_html = f'<p class="hero__lead">{lead}</p>' if lead else ""
    return f"""<section class="page-hero">
    {picture(image, list(widths), "", cls="page-hero__bg", eager=True)}
    <div class="container page-hero__inner">
      {breadcrumbs(page)}
      {eyebrow_html}
      <h1>{title}</h1>
      {lead_html}{actions}
    </div>
  </section>"""


def p_trust_bar(page):
    items = [
        ("clock", "Same-week scheduling", "Most jobs booked within 2&ndash;3 days"),
        ("shield", "Insured &amp; accountable", "Clear quotes before any work starts"),
        ("camera", "Photo updates", "Ideal for landlords, realtors &amp; remote owners"),
        ("broom", "Tidy, protected work zones", "Floor protection and HEPA dust control"),
    ]
    lis = "".join(
        f'<li>{icon(i)}<div><strong>{t}</strong><span>{d}</span></div></li>' for i, t, d in items)
    return f'<section class="trust-bar" aria-label="Why homeowners choose ReadyFix"><ul class="container">{lis}</ul></section>'


def service_card(slug):
    s = SERVICE_BY_SLUG[slug]
    return (f'<li><a class="service-card" href="/services/{slug}/">{icon(s[4], "service-card__icon")}'
            f'<h3>{s[2]}</h3><p>{s[3]}</p><span class="service-card__more">Learn more {icon("arrow")}</span></a></li>')


def p_services_grid(page, heading="Handyman services in Toronto", intro="", eyebrow="What we fix", level="h2"):
    cards = "".join(service_card(s[0]) for s in SERVICES)
    intro_html = f"<p>{intro}</p>" if intro else ""
    return f"""<section class="section" id="services" aria-labelledby="services-title">
    <div class="container">
      <div class="section-head">
        <p class="eyebrow">{eyebrow}</p>
        <{level} id="services-title">{heading}</{level}>
        {intro_html}
      </div>
      <ul class="card-grid">{cards}</ul>
    </div>
  </section>"""


def p_related_services(page, heading="Other handyman services"):
    current = page.get("service")
    cards = "".join(service_card(s[0]) for s in SERVICES if s[0] != current)
    return f"""<section class="section section--alt" aria-labelledby="related-title">
    <div class="container">
      <div class="section-head">
        <p class="eyebrow">Bundle and save a trip</p>
        <h2 id="related-title">{heading}</h2>
        <p>Most visits cover more than one item. Add anything from your list and we'll quote it together.</p>
      </div>
      <ul class="card-grid card-grid--compact">{cards}</ul>
    </div>
  </section>"""


def p_areas(page, heading="Areas we serve", intro=None):
    current = page.get("area")
    intro = intro or ("ReadyFix is based in Toronto and books jobs across the city and nearby GTA. "
                      "Pick your area to see local details.")
    cur = ' aria-current="page"'
    links = "".join(
        f'<li><a href="/areas/{slug}/"{cur if slug == current else ""}>{icon("pin")}{name}</a></li>'
        for slug, name, _ in AREAS)
    return f"""<section class="section section--alt" aria-labelledby="areas-title">
    <div class="container">
      <div class="section-head">
        <p class="eyebrow">Toronto &amp; the GTA</p>
        <h2 id="areas-title">{heading}</h2>
        <p>{intro}</p>
      </div>
      <ul class="area-list">{links}</ul>
    </div>
  </section>"""


def p_testimonials(page, heading="What Toronto homeowners say"):
    figs = "".join(
        f'<figure class="quote-card"><div class="quote-card__stars" aria-hidden="true">{icon("star") * 5}</div>'
        f'<blockquote>{q}</blockquote><figcaption><strong>{n}</strong> &middot; {where}</figcaption></figure>'
        for q, n, where in TESTIMONIALS)
    return f"""<section class="section" aria-labelledby="reviews-title">
    <div class="container">
      <div class="section-head">
        <p class="eyebrow">Reviews</p>
        <h2 id="reviews-title">{heading}</h2>
      </div>
      <div class="quote-grid">{figs}</div>
      <p class="section-foot"><a class="text-link" href="{HOMESTARS}" target="_blank" rel="noopener">Read more reviews on HomeStars {icon("arrow")}</a></p>
    </div>
  </section>"""


def p_process(page, heading="How a ReadyFix visit works"):
    steps = [
        ("Send photos", "Text or email pictures of each item. A quick look lets us quote accurately and bring the right materials."),
        ("Get a clear quote", "You get a written price and a choice of arrival windows, usually within one business day."),
        ("We fix it", "We arrive on time, protect floors, work clean, and finish as much as possible in a single visit."),
        ("Walk-through", "We review the work with you (or send photos if you're remote) and invoice online."),
    ]
    lis = "".join(f"<li><h3>{t}</h3><p>{d}</p></li>" for t, d in steps)
    return f"""<section class="section section--alt" aria-labelledby="process-title">
    <div class="container">
      <div class="section-head">
        <p class="eyebrow">Simple from start to finish</p>
        <h2 id="process-title">{heading}</h2>
      </div>
      <ol class="steps">{lis}</ol>
    </div>
  </section>"""


def p_cta(page, heading="Need it fixed this week?", text="Call or text for a quote and a confirmed arrival window."):
    return f"""<section class="cta-band" aria-labelledby="cta-title">
    <div class="container cta-band__inner">
      <div>
        <h2 id="cta-title">{heading}</h2>
        <p>{text}</p>
      </div>
      <div class="cta-band__actions">
        <a class="btn btn--light btn--lg" data-track="cta:call" href="tel:{TEL}">{icon("phone")}Call {PHONE}</a>
        <a class="btn btn--outline-light btn--lg" href="sms:{TEL}">{icon("message")}Text a photo</a>
      </div>
    </div>
  </section>"""


def p_contact(page, heading="Get a free quote", intro="Tell us what needs fixing. Photos help us quote accurately.",
              message_label="What needs fixing?"):
    return f"""<section id="contact" class="section contact" aria-labelledby="contact-title">
    <div class="container contact__inner">
      <div class="contact__info">
        <p class="eyebrow">Contact</p>
        <h2 id="contact-title">{heading}</h2>
        <p>{intro}</p>
        <ul class="contact__list">
          <li>{icon("phone")}<div><span>Call or text</span><a data-track="cta:call" href="tel:{TEL}">{PHONE}</a></div></li>
          <li>{icon("message")}<div><span>Email</span><a href="mailto:{EMAIL}">{EMAIL}</a></div></li>
          <li>{icon("clock")}<div><span>Hours</span>Mon&ndash;Fri, 9am&ndash;5pm</div></li>
          <li>{icon("pin")}<div><span>Service area</span>Toronto &amp; the GTA</div></li>
        </ul>
      </div>
      <form class="contact-form" action="{FORM_ACTION}" method="POST" data-track="cta:form_submit">
        <input type="hidden" name="_subject" value="New quote request from readyfix.ca">
        <input type="hidden" name="_redirect" value="{BASE}/thanks.html">
        <input type="hidden" name="page" value="{esc(page['url'])}">
        <div class="field-row">
          <div class="field"><label for="cf-name">Name</label><input id="cf-name" name="name" type="text" autocomplete="name" required></div>
          <div class="field"><label for="cf-phone">Phone</label><input id="cf-phone" name="phone" type="tel" autocomplete="tel"></div>
        </div>
        <div class="field"><label for="cf-email">Email</label><input id="cf-email" name="email" type="email" autocomplete="email" required></div>
        <div class="field"><label for="cf-address">Neighbourhood or address</label><input id="cf-address" name="address" type="text" autocomplete="address-line1"></div>
        <div class="field"><label for="cf-message">{message_label}</label><textarea id="cf-message" name="message" rows="5" required></textarea></div>
        <div class="hp" aria-hidden="true"><label for="cf-company">Leave blank</label><input id="cf-company" name="company" type="text" tabindex="-1" autocomplete="off"></div>
        <button class="btn btn--primary btn--lg btn--block" type="submit">Send my request</button>
        <p class="form-note">We reply within one business day. Prefer to text photos? <a href="sms:{TEL}">Text {PHONE}</a>.</p>
        <p class="form-status" aria-live="polite"></p>
      </form>
    </div>
  </section>"""


PARTIALS = {
    "page_hero": p_page_hero, "trust_bar": p_trust_bar, "services_grid": p_services_grid,
    "related_services": p_related_services, "areas": p_areas, "testimonials": p_testimonials,
    "process": p_process, "cta": p_cta, "contact": p_contact,
}


def expand_partials(body, page):
    def repl(m):
        name, raw = m.group(1), (m.group(2) or "").strip()
        args = json.loads(raw) if raw else {}
        if name not in PARTIALS:
            sys.exit(f"{page['src']}: unknown partial '{name}'")
        return PARTIALS[name](page, **args)
    return re.sub(r"<!--@(\w+)\s*(\{.*?\})?\s*-->", repl, body, flags=re.S)


# ------------------------------------------------------------------ layout

def nav_current(page, key):
    return ' aria-current="page"' if page.get("nav") == key else ""


def header(page):
    svc_links = "".join(
        f'<li><a href="/services/{s[0]}/"{nav_current(page, s[0])}>{icon(s[4])}{s[1]}</a></li>' for s in SERVICES)
    area_links = "".join(
        f'<li><a href="/areas/{a[0]}/"{nav_current(page, a[0])}>{a[1]}</a></li>' for a in AREAS)
    in_services = page.get("nav") == "services" or "service" in page
    in_areas = "area" in page
    contact_href = "#contact" if page.get("has_contact") else "/#contact"
    return f"""<header class="site-header">
    <div class="container site-header__inner">
      <a class="logo" href="/" aria-label="ReadyFix Handyman Services, home">
        <picture><source type="image/webp" srcset="/img/logo.webp"><img src="/img/logo.png" alt="ReadyFix Handyman Services" width="163" height="48"></picture>
      </a>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">{icon("menu")}<span class="sr-only">Menu</span></button>
      <nav class="site-nav" id="site-nav" aria-label="Primary">
        <ul class="site-nav__list">
          <li class="has-menu{' is-current' if in_services else ''}">
            <a href="/services/"{nav_current(page, "services")}>Services</a>
            <button class="submenu-toggle" type="button" aria-expanded="false" aria-label="Show services">{icon("chevron")}</button>
            <ul class="submenu submenu--wide">{svc_links}</ul>
          </li>
          <li class="has-menu{' is-current' if in_areas else ''}">
            <a href="/areas/"{nav_current(page, "areas")}>Areas</a>
            <button class="submenu-toggle" type="button" aria-expanded="false" aria-label="Show service areas">{icon("chevron")}</button>
            <ul class="submenu">{area_links}</ul>
          </li>
          <li><a href="/pricing/"{nav_current(page, "pricing")}>Pricing</a></li>
          <li><a href="/about/"{nav_current(page, "about")}>About</a></li>
          <li><a href="{contact_href}">Contact</a></li>
        </ul>
      </nav>
      <a class="btn btn--primary header-call" data-track="cta:call" href="tel:{TEL}">{icon("phone")}<span>{PHONE}</span></a>
    </div>
  </header>"""


def footer(page):
    svc = "".join(f'<li><a href="/services/{s[0]}/">{s[2]}</a></li>' for s in SERVICES)
    areas = "".join(f'<li><a href="/areas/{a[0]}/">Handyman in {a[1]}</a></li>' for a in AREAS)
    year = dt.date.today().year
    return f"""<footer class="site-footer">
    <div class="container footer-grid">
      <div class="footer-brand">
        <picture><source type="image/webp" srcset="/img/logo-light.webp"><img src="/img/logo-light.png" alt="ReadyFix Handyman Services" width="163" height="48" loading="lazy"></picture>
        <p>Toronto handyman for drywall repair, cabinets, doors, trim, mounting and real-estate punch lists.</p>
        <address>
          <a data-track="cta:call" href="tel:{TEL}">{icon("phone")}{PHONE}</a>
          <a href="mailto:{EMAIL}">{icon("message")}{EMAIL}</a>
          <span>{icon("clock")}Mon&ndash;Fri 9am&ndash;5pm</span>
          <span>{icon("pin")}Toronto, ON &middot; serving the GTA</span>
        </address>
      </div>
      <div>
        <h2 class="footer-heading">Services</h2>
        <ul>{svc}</ul>
      </div>
      <div>
        <h2 class="footer-heading">Service areas</h2>
        <ul>{areas}</ul>
      </div>
      <div>
        <h2 class="footer-heading">Company</h2>
        <ul>
          <li><a href="/about/">About ReadyFix</a></li>
          <li><a href="/pricing/">Pricing &amp; quotes</a></li>
          <li><a href="/before-after/">Before &amp; after</a></li>
          <li><a href="/services/">All services</a></li>
          <li><a href="{HOMESTARS}" target="_blank" rel="noopener">HomeStars reviews</a></li>
          <li><a href="{INSTAGRAM}" target="_blank" rel="noopener">Instagram</a></li>
        </ul>
      </div>
    </div>
    <div class="container footer-bottom">
      <p>&copy; {year} ReadyFix Handyman Services. All rights reserved.</p>
      <a href="/sitemap.xml">Sitemap</a>
    </div>
  </footer>

  <div class="mobile-cta" aria-label="Quick contact">
    <a class="btn btn--primary" data-track="cta:call" href="tel:{TEL}">{icon("phone")}Call</a>
    <a class="btn btn--dark" href="sms:{TEL}">{icon("message")}Text a photo</a>
  </div>"""


# ------------------------------------------------------------------ JSON-LD

def business_node():
    return {
        "@type": "HomeAndConstructionBusiness",
        "@id": BIZ_ID,
        "name": "ReadyFix Handyman Services",
        "alternateName": ["Ready Fix Handyman Services", "ReadyFix Handyman"],
        "description": "Toronto handyman for drywall repair, cabinet and door fixes, trim, TV mounting, lock replacement and real-estate punch lists.",
        "url": f"{BASE}/",
        "logo": f"{BASE}/img/logo.png",
        "image": f"{BASE}/img/og-image.jpg",
        "telephone": TEL,
        "email": EMAIL,
        "address": {"@type": "PostalAddress", "addressLocality": "Toronto",
                    "addressRegion": "ON", "addressCountry": "CA"},
        "areaServed": [{"@type": "City", "name": a[2]} for a in AREAS],
        "openingHoursSpecification": [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "09:00", "closes": "17:00"}],
        "hasOfferCatalog": {
            "@type": "OfferCatalog", "name": "Handyman services",
            "itemListElement": [{"@type": "Offer", "itemOffered": {
                "@type": "Service", "name": s[5], "url": f"{BASE}/services/{s[0]}/"}} for s in SERVICES]},
        "sameAs": [INSTAGRAM, HOMESTARS],
    }


def faq_node(body):
    items = re.findall(r'<details class="faq__item"[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>', body, re.S)
    if not items:
        return None
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": plain(q), "acceptedAnswer": {"@type": "Answer", "text": plain(a)}}
        for q, a in items]}


def jsonld(page, body):
    url = BASE + page["url"]
    graph = [business_node(), {
        "@type": "WebSite", "@id": f"{BASE}/#website", "url": f"{BASE}/",
        "name": "ReadyFix Handyman Services", "publisher": {"@id": BIZ_ID}, "inLanguage": "en-CA"}]
    graph.append({
        "@type": "WebPage", "@id": url + "#webpage", "url": url, "name": page["title"],
        "description": page["description"], "inLanguage": "en-CA",
        "isPartOf": {"@id": f"{BASE}/#website"}, "about": {"@id": BIZ_ID},
        "primaryImageOfPage": {"@type": "ImageObject", "url": BASE + page.get("og_image", "/img/og-image.jpg")}})
    if "service" in page:
        s = SERVICE_BY_SLUG[page["service"]]
        graph.append({
            "@type": "Service", "@id": url + "#service", "name": f"{s[5]} in Toronto", "serviceType": s[5],
            "description": page["description"], "url": url, "provider": {"@id": BIZ_ID},
            "areaServed": [{"@type": "City", "name": a[2]} for a in AREAS]})
    if "area" in page:
        a = AREA_BY_SLUG[page["area"]]
        graph.append({
            "@type": "Service", "@id": url + "#service", "name": f"Handyman services in {a[1]}",
            "serviceType": "Handyman", "description": page["description"], "url": url,
            "provider": {"@id": BIZ_ID}, "areaServed": {"@type": "Place", "name": f"{a[1]}, Ontario"}})
    if page.get("crumbs"):
        items = [("Home", "/")] + [tuple(c) for c in page["crumbs"]]
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i, "name": plain(n), "item": BASE + (u or page["url"])}
            for i, (n, u) in enumerate(items, 1)]})
    faq = faq_node(body)
    if faq:
        graph.append(faq)
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ page

def head(page, body):
    title, desc = esc(page["title"]), esc(page["description"])
    canonical = BASE + page["url"] if page.get("url") else None
    og_image = BASE + page.get("og_image", "/img/og-image.jpg")
    robots = page.get("robots", "index, follow, max-image-preview:large")
    lines = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{title}</title>",
        f'<meta name="description" content="{desc}">',
        f'<meta name="robots" content="{robots}">',
    ]
    if canonical:
        lines.append(f'<link rel="canonical" href="{canonical}">')
    lines += [
        '<meta name="theme-color" content="#e1232b">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">',
        '<link rel="stylesheet" href="/css/main.css">',
        '<script defer src="/js/main.js"></script>',
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
        '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">',
        '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">',
        '<link rel="manifest" href="/site.webmanifest">',
    ]
    if not page.get("minimal"):
        lines += [
            '<meta name="geo.region" content="CA-ON">',
            '<meta name="geo.placename" content="Toronto">',
            '<meta property="og:locale" content="en_CA">',
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="ReadyFix Handyman Services">',
            f'<meta property="og:title" content="{title}">',
            f'<meta property="og:description" content="{desc}">',
            f'<meta property="og:url" content="{canonical}">',
            f'<meta property="og:image" content="{og_image}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{title}">',
            f'<meta name="twitter:description" content="{desc}">',
            f'<meta name="twitter:image" content="{og_image}">',
        ]
    lines += [
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>',
        "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
        f"gtag('js',new Date());gtag('config','{GA_ID}');</script>",
    ]
    if not page.get("minimal"):
        lines.append(f'<script type="application/ld+json">\n{jsonld(page, body)}\n</script>')
    return "\n  ".join(lines)


def render(page):
    body = expand_partials(page["body"], page)
    # Source comments (notes, TODOs for the owner) stay in src/, not in the published HTML.
    body = re.sub(r"\s*<!--.*?-->", "", body, flags=re.S)
    page["has_contact"] = 'id="contact"' in body
    if page.get("minimal"):
        chrome_top, chrome_bottom = "", ""
    else:
        chrome_top, chrome_bottom = header(page), footer(page)
    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
  {head(page, body)}
</head>
<body>
  {icon_sprite()}
  <a class="skip-link" href="#main">Skip to main content</a>
  {chrome_top}
  <main id="main">
  {body.strip()}
  </main>
  {chrome_bottom}
</body>
</html>
"""


def load(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--\s*(\{.*?\})\s*-->", text, re.S)
    if not m:
        sys.exit(f"{path}: missing JSON front matter comment")
    page = json.loads(m.group(1))
    rel = path.relative_to(SRC).as_posix()
    page["src"] = rel
    page["out"] = rel
    if "url" not in page:
        page["url"] = "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)
    page["body"] = text[m.end():]
    page["mtime"] = dt.date.fromtimestamp(path.stat().st_mtime).isoformat()
    for key in ("title", "description"):
        if key not in page:
            sys.exit(f"{rel}: missing '{key}'")
    return page


def write_sitemap(pages):
    entries = sorted((p for p in pages if "sitemap" in p), key=lambda p: (-p["sitemap"], p["url"]))
    body = "".join(
        f"  <url>\n    <loc>{BASE}{p['url']}</loc>\n    <lastmod>{p['mtime']}</lastmod>\n"
        f"    <priority>{p['sitemap']:.1f}</priority>\n  </url>\n" for p in entries)
    with open(ROOT / "sitemap.xml", "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")
    return len(entries)


def main():
    pages = [load(p) for p in sorted(SRC.rglob("*.html"))]
    for page in pages:
        out = ROOT / page["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(page))
    n = write_sitemap(pages)
    print(f"built {len(pages)} pages, {n} in sitemap.xml")


if __name__ == "__main__":
    main()
