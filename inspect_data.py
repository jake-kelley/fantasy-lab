from pipeline.data import Sources
from collections import Counter

s = Sources()
for year in [2024, 2025, 2026]:
    for tag, name in [('stats_player', f'stats_player_week_{year}.csv'),
                      ('stats_team', f'stats_team_week_{year}.csv'),
                      ('snap_counts', f'snap_counts_{year}.csv')]:
        rows = s.csv(tag, name)
        print(name, len(rows), list(rows[0])[:18], 'weeks', dict(Counter(x.get('week') for x in rows)))
        if tag == 'snap_counts':
            print('snap sample', rows[0])
rows = s.csv('players', 'players.csv')
print('players', len(rows), list(rows[0]))
rows = s.csv('schedules', 'games.csv', ttl=3600)
print('games', len(rows), list(rows[0]))
