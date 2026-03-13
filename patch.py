
f = open('output/jobs.html', 'r')
h = f.read()
f.close()

h = h.replace(
    '.new-mode-active .comp-filter,\n    .new-mode-active .time-filter,\n    .new-mode-active .search-box,\n    .new-mode-active .search-clear {',
    '.new-mode-active .time-filter {'
)
h = h.replace(
    '_deactivateNewTab();\n        // Update active class',
    '// Update active class'
)
h = h.replace(
    '!currentState.newOnly && currentState.company !== \'all\'',
    'currentState.company !== \'all\''
)

f = open('output/jobs.html', 'w')
f.write(h)
f.close()
print('patched')
