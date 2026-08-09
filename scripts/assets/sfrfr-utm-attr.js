/**
 * First-party cookie атрибуции sfrfr_attr (90 дней).
 * Без ПДн — только UTM и сегмент. Подключается MU-plugin'ом формы.
 */
(function () {
  var COOKIE = "sfrfr_attr";
  var DAYS = 90;

  function read() {
    var m = document.cookie.match(/(?:^|; )sfrfr_attr=([^;]*)/);
    if (!m) return {};
    try {
      return JSON.parse(decodeURIComponent(m[1])) || {};
    } catch (e) {
      return {};
    }
  }

  function write(obj) {
    var maxAge = DAYS * 24 * 60 * 60;
    document.cookie =
      COOKIE +
      "=" +
      encodeURIComponent(JSON.stringify(obj)) +
      "; path=/; max-age=" +
      maxAge +
      "; SameSite=Lax";
  }

  function pick(params, key) {
    var v = params.get(key);
    return v ? String(v).slice(0, 120) : "";
  }

  try {
    var params = new URLSearchParams(window.location.search);
    var cur = read();
    var now = new Date().toISOString();
    var src = pick(params, "utm_source");
    var med = pick(params, "utm_medium");
    var camp = pick(params, "utm_campaign");
    var content = pick(params, "utm_content");
    var term = pick(params, "utm_term");
    var seg = pick(params, "audience_segment");
    var land = pick(params, "landing_variant");
    var region = pick(params, "region_bucket");
    var ref = pick(params, "referral_code");
    if (!(src || med || camp || seg || land || ref)) return;
    if (!cur.first_source && src) {
      cur.first_source = src;
      cur.first_touch_at = now;
    }
    if (src) cur.last_source = src;
    if (med) cur.utm_medium = med;
    if (camp) cur.utm_campaign = camp;
    if (content) cur.utm_content = content;
    if (term) cur.utm_term = term;
    if (seg) cur.audience_segment = seg;
    if (land) cur.landing_variant = land;
    if (region) cur.region_bucket = region;
    if (ref) cur.referral_code = ref;
    cur.last_touch_at = now;
    write(cur);
  } catch (e) {
    /* ignore */
  }
})();
