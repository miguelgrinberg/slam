import jinja2

jinja_env = jinja2.Environment(lstrip_blocks=True, trim_blocks=True)


def render_template(template, **kwargs):
    return jinja_env.from_string(template).render(**kwargs)
