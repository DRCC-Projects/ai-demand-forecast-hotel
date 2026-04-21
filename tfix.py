with open('dashboard/app.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(
    "'modeBarButtonsToRemove': ['select2d', 'lasso2d'],\n        'displaylogo': False\n    })",
    "'modeBarButtonsToRemove': ['select2d', 'lasso2d'],\n        'displaylogo': False,\n        'scrollZoom': True\n    })"
)
with open('dashboard/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Done')
