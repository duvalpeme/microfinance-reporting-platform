{#- Utilise le schéma demandé tel quel (silver, quarantine) au lieu de <schéma_cible>_<schéma>. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
