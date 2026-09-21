import app.crud.classes as classes

# Debug
print("Module file:", classes.__file__)
print("Module attrs:", [attr for attr in dir(classes) if not attr.startswith('_')])

# Check if search_classes exists
if hasattr(classes, 'search_classes'):
    print("search_classes exists")
else:
    print("search_classes NOT FOUND")