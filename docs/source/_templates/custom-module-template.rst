{{ fullname | escape | underline}}

.. automodule:: {{ fullname }}
   {%- if fullname=='iblrig_tasks' %}
   :private-members:
   {% endif %}

   {% block attributes %}
   {%- if attributes %}
   .. rubric:: {{ _('Module Attributes') }}

   .. autosummary::
      :nosignatures:
      :toctree:
   {% for item in attributes %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

   {%- block functions %}
   {%- if functions %}
   .. rubric:: {{ _('Functions') }}

   .. autosummary::
      :nosignatures:
      :toctree:
   {% for item in functions %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

   {%- block classes %}
   {%- if classes %}
   .. rubric:: {{ _('Classes') }}

   .. autosummary::
      :nosignatures:
      :toctree:
      :template: custom-class-template.rst
   {% for item in classes %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

   {%- block exceptions %}
   {%- if exceptions %}
   .. rubric:: {{ _('Exceptions') }}

   .. autosummary::
      :nosignatures:
      :toctree:
   {% for item in exceptions %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

{%- block modules %}
{%- if modules %}
.. rubric:: Modules

.. autosummary::
   :nosignatures:
   :toctree:
   :template: custom-module-template.rst
   :recursive:
{% for item in modules %}
   {{ item }}
{%- endfor %}
{% endif %}
{%- endblock %}
