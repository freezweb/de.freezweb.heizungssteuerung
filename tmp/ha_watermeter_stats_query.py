import sqlite3
con=sqlite3.connect('/config/home-assistant_v2.db')
con.row_factory=sqlite3.Row
cur=con.cursor()
print('statistics_meta watermeter:')
for row in cur.execute("select id, statistic_id, source, unit_of_measurement, has_sum, has_mean from statistics_meta where statistic_id like '%watermeter%' or statistic_id like '%zaehler%' order by statistic_id"):
    print(dict(row))
print('states_meta watermeter:')
for row in cur.execute("select metadata_id, entity_id from states_meta where entity_id like '%watermeter%' or entity_id like '%zaehler%' order by entity_id"):
    print(dict(row))
con.close()
