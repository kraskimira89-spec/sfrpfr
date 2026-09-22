# 2026-09-22 вЂ” ads в†’ РєР°РЅР°Р»: PR, РіР»Р°РІРЅР°СЏ, UTM, Р·Р°РєСЂРµРї

## РЎРґРµР»Р°РЅРѕ РІ РєРѕРґРµ

- Р“Р»Р°РІРЅР°СЏ: primary В«РџРѕРґРїРёСЃР°С‚СЊСЃСЏ РЅР° РєР°РЅР°Р» MAXВ» (hero + Р±Р»РѕРє СЃРІСЏР·Рё).
- `wp_apply_home.php`: UTM `max_channel_subscribe` РґР»СЏ `home_hero` / `home_max_guide`.
- Р—Р°РєСЂРµРї `00-pinned`: РєРЅРѕРїРєР° В«РџРѕРґР°С‚СЊ Р·Р°СЏРІРєСѓВ».
- Р‘СЂРёС„С‹ Р”РёСЂРµРєС‚ / UTM playbook.

## Р’Р»Р°РґРµР»РµС† (СЂРµРєР»Р°РјР° РІРЅРµ СЂРµРїРѕ)

РџРµСЂРµРІРµСЃС‚Рё destination Р°РєС‚РёРІРЅС‹С… РѕР±СЉСЏРІР»РµРЅРёР№ РЅР°:

```text
https://max.ru/channel_proverkastaza?utm_source=<src>&utm_medium=<med>&utm_campaign=max_channel_subscribe&utm_content=<place>
```

РќРµ РІРµСЃС‚Рё С…РѕР»РѕРґРЅС‹Р№ С‚СЂР°С„РёРє РЅР° `id8905998693_1_bot`.

## РџРѕСЃР»Рµ deploy

- Seed home: `vps_deploy.sh` в†’ `wp_apply_landing_vps.sh` (РїСЂРѕРІРµСЂРµРЅРѕ live: primary CTA в†’ РєР°РЅР°Р» + UTM `home_hero` / `home_max_guide`).
- Р—Р°РєСЂРµРї republish: `sfrfr max-channel-publish-starter --direct --only 00-pinned` в†’ mid `mid.ffffb970e931d56801a0c80b806c4afe`, pin `success`, РїРѕСЃС‚ https://max.ru/channel_proverkastaza/AaDIC4BsSv4 (РєРЅРѕРїРєР° В«РџРѕРґР°С‚СЊ Р·Р°СЏРІРєСѓВ» в†’ `MAX_CHAT_URL`).

