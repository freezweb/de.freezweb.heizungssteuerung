from pathlib import Path
path = Path('/opt/heizung/config/settings.yaml')
text = path.read_text(encoding='utf-8')
block = '''  watermeter_http:
    enabled: true
    url: "http://10.1.20.191/value?all=true&type=value"
    number_name: "zaehlerstand"
    total_scale_l_per_unit: 1000
    timeout_s: 2.0
    poll_interval_s: 10.0
    mqtt_mirror_enabled: true
    mqtt_topic_base: "watermeter/zaehlerstand"
'''
if '  watermeter_http:' not in text:
    marker = '  flow_modbus:\n'
    start = text.index(marker)
    next_top = text.index('\nintercpu:', start)
    text = text[:next_top + 1] + block + text[next_top + 1:]
else:
    start = text.index('  watermeter_http:')
    end = text.find('\n  ', start + 1)
    top = text.find('\nintercpu:', start + 1)
    candidates = [x for x in (end, top) if x != -1]
    end = min(candidates) if candidates else len(text)
    text = text[:start] + block.rstrip('\n') + text[end:]
path.write_text(text, encoding='utf-8')
print('settings watermeter_http enabled')
