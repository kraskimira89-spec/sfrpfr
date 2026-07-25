{% materialization view, default %}
  {# Avoid dbt's tmp/rename/backup dance: on Supabase it contends on pg_type
     (statement timeout / hang on ALTER ... RENAME). CREATE OR REPLACE is enough. #}
  {%- set target_relation = this.incorporate(type='view') -%}
  {%- set existing_relation = load_relation(this) -%}

  {% if existing_relation is not none and existing_relation.type != 'view' %}
    {{ adapter.drop_relation(existing_relation) }}
  {% endif %}

  {{ run_hooks(pre_hooks, inside_transaction=False) }}
  {{ run_hooks(pre_hooks, inside_transaction=True) }}

  {% call statement('main') -%}
    create or replace view {{ target_relation }} as (
      {{ sql }}
    )
  {%- endcall %}

  {{ run_hooks(post_hooks, inside_transaction=True) }}
  {{ adapter.commit() }}
  {{ run_hooks(post_hooks, inside_transaction=False) }}

  {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
