{{ fullname | escape | underline}}

.. automodule:: {{ fullname }}
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
{%- if modules or name == 'iblrig_tasks' %}
.. rubric:: Modules

.. autosummary::
   :nosignatures:
   :toctree:
   :template: custom-module-template.rst
   :recursive:
{% for item in modules %}
   {%- if item != 'test' %} {# EXCLUDE TESTS FROM API #}
   {{ item }}
   {% endif %}
{%- endfor %}
{%- if name == 'iblrig_tasks' %}
   _iblrig_tasks_advancedChoiceWorld
   _iblrig_tasks_biasedChoiceWorld
   _iblrig_tasks_ephysChoiceWorld
   _iblrig_tasks_habituationChoiceWorld
   _iblrig_tasks_ImagingChoiceWorld
   _iblrig_tasks_neuroModulatorChoiceWorld
   _iblrig_tasks_passiveChoiceWorld
   _iblrig_tasks_spontaneous
   _iblrig_tasks_trainingChoiceWorld
   _iblrig_tasks_trainingPhaseChoiceWorld
{% endif %}
{% endif %}
{%- endblock %}
