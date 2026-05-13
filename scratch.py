import os
import glob

snippet = """
    <!-- TOAST NOTIFICATIONS -->
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div id="toast-container" class="fixed top-5 right-5 z-50 flex flex-col gap-3">
          {% for category, message in messages %}
            {% set bg_color = 'bg-blue-600' %}
            {% set text_color = 'text-white' %}
            {% if category == 'success' %}
              {% set bg_color = 'bg-green-600' %}
            {% elif category == 'error' or category == 'danger' %}
              {% set bg_color = 'bg-red-600' %}
            {% elif category == 'warning' %}
              {% set bg_color = 'bg-yellow-500' %}
              {% set text_color = 'text-gray-900' %}
            {% endif %}
            <div class="toast-message flex items-center p-4 w-full max-w-xs rounded-lg shadow-lg opacity-100 transition-opacity duration-500 ease-in-out {{ bg_color }} {{ text_color }}" role="alert">
              <div class="text-sm font-medium">{{ message }}</div>
              <button type="button" class="ml-auto -mx-1.5 -my-1.5 bg-transparent hover:opacity-75 rounded-lg focus:ring-2 focus:ring-gray-300 p-1.5 inline-flex h-8 w-8" onclick="this.parentElement.remove();" aria-label="Close">
                <span class="sr-only">Close</span>
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
              </button>
            </div>
          {% endfor %}
        </div>
        <script>
          document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
              var toasts = document.querySelectorAll('.toast-message');
              toasts.forEach(function(toast) {
                toast.classList.remove('opacity-100');
                toast.classList.add('opacity-0');
                setTimeout(function() { toast.remove(); }, 500);
              });
            }, 4000);
          });
        </script>
      {% endif %}
    {% endwith %}
"""

for filepath in glob.glob("app/templates/**/*.html", recursive=True):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "<!-- TOAST NOTIFICATIONS -->" in content:
        continue
    
    # Replace </body> with the snippet + </body>
    if "</body>" in content:
        new_content = content.replace("</body>", snippet + "\n</body>")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Injected into {filepath}")
    else:
        print(f"Skipped {filepath} (no </body> tag found)")
