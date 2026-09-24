
with open('gui/main_window.py', encoding='utf-8') as f:
    content = f.read()

old = 'lbl_status.setText(f"Za\u0142adowano szablon \u201e{p.name}\u201d. Kliknij \u201ePor\u00f3wnaj zawarto\u015b\u0107\u201d.")\n\n    def _save_current_as_profile(self):'
new = 'lbl_status.setText(f"Za\u0142adowano szablon \u201e{p.name}\u201d. Kliknij \u201ePor\u00f3wnaj zawarto\u015b\u0107\u201d.")\n\n        settings = load_settings()\n        if settings.auto_compare_on_profile_load:\n            self._start_compare()\n\n    def _save_current_as_profile(self):'

if old in content:
    content = content.replace(old, new, 1)
    with open('gui/main_window.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: auto_compare_on_profile_load integrated')
else:
    print('ERROR: target string not found in file')
    # debug: print context
    idx = content.find('save_current_as_profile')
    print('Context before save_current_as_profile:')
    print(repr(content[idx-300:idx]))
