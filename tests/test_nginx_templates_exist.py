from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_nginx_templates_exist():
    conf = PROJECT_ROOT / "deploy" / "nginx" / "renatapromotion.conf"
    limits = PROJECT_ROOT / "deploy" / "nginx" / "limits.conf"
    assert conf.exists(), conf
    assert limits.exists(), limits


def test_nginx_template_contains_vhosts_and_headers():
    conf = (PROJECT_ROOT / "deploy" / "nginx" / "renatapromotion.conf").read_text(encoding="utf-8")
    assert 'server_name crm.<domain>;' in conf
    assert 'server_name api.<domain>;' in conf
    assert 'add_header X-Renata-VHost "crm" always;' in conf
    assert 'add_header X-Renata-VHost "api" always;' in conf
