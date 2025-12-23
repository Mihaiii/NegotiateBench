from fasthtml.common import *
import markdown
from db.service import (
    get_negotiations_leaderboard_all,
    get_negotiations_leaderboard_latest,
)

with open("README.md", "r") as f:
    readme_content = f.read()
readme_content = readme_content.replace("# **NegotiateBench**", "")
parsed_md = markdown.markdown(readme_content, extensions=["codehilite", "fenced_code"])
hdrs = (HighlightJS(langs=["python", "javascript", "html", "css"]),)

app, rt = fast_app(pico=False, hdrs=hdrs)

theme_script = Script("""
(function() {
    const getTheme = () => localStorage.getItem('theme') || 'dark';
    
    const setTheme = (theme) => {
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
        const icon = document.getElementById('theme-icon');
        if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    };
    
    const toggleTheme = () => {
        const current = document.documentElement.getAttribute('data-bs-theme') || getTheme();
        setTheme(current === 'dark' ? 'light' : 'dark');
    };
    
    const handleNavClick = function(e) {
        e.preventDefault();
        const url = this.getAttribute('hx-get') || this.dataset.url;
        const target = this.getAttribute('hx-target') || '#content';
        if (!url) return false;
        
        const targetEl = document.querySelector(target);
        if (!targetEl) return false;
        
        fetch(url)
            .then(r => r.text())
            .then(html => targetEl.innerHTML = html)
            .catch(() => targetEl.innerHTML = '<p class="text-danger">Error loading content</p>');
        return false;
    };
    
    const initNav = () => {
        document.querySelectorAll('a.nav-link[href="#"]').forEach(link => {
            link.onclick = handleNavClick;
        });
    };
    
    const init = () => {
        setTheme(getTheme());
        const themeBtn = document.getElementById('theme-toggle');
        if (themeBtn) themeBtn.onclick = toggleTheme;
        initNav();
    };
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    document.body?.addEventListener('htmx:load', initNav);
})();
""")

@rt("/")
def get():
    return Html(
        Head(
            Title("NegotiateBench"),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
            ),
            Style("""
                .nav li {
                    list-style: none;
                }
            """),
            theme_script,
        ),
        Body(
            Div(
                Div(
                    H1("NegotiateBench", cls="text-center my-4"),
                    Button(
                        Span("🌙", id="theme-icon"),
                        id="theme-toggle",
                        cls="btn btn-outline-secondary position-absolute top-0 end-0 m-3",
                        type="button",
                    ),
                    cls="position-relative",
                ),
                Ul(
                    Li(
                        A(
                            "About",
                            href="#",
                            hx_get="/about",
                            hx_target="#content",
                            data_url="/about",
                            cls="nav-link",
                        )
                    ),
                    Li(
                        A(
                            "Leaderboard",
                            href="#",
                            hx_get="/leaderboard",
                            hx_target="#content",
                            data_url="/leaderboard",
                            cls="nav-link",
                        )
                    ),
                    cls="nav nav-tabs justify-content-center",
                ),
                Div(Div(NotStr(parsed_md), cls="mt-4"), id="content"),
                cls="container",
            )
        ),
    )


@rt("/about")
def get():
    return Div(NotStr(parsed_md), cls="mt-4")


@rt("/leaderboard")
def get():
    latest = get_negotiations_leaderboard_latest()
    overall = get_negotiations_leaderboard_all()

    def build_table(title, rows):
        table_rows = [
            Tr(
                Td(r["rank"]),
                Td(r["model_name"]),
                Td(f'{r["profit_percentage"]:.2f}%'),
                Td(f'{r["max_possible_profit"]:.2f}'),
                Td(f'{r["total_profit"]:.2f}'),
                Td(A("link", href=r["code_link"], target="_blank")) if r.get("code_link") else Td(""),
            )
            for r in rows
        ]
        return Div(
            H3(title, cls="mt-4"),
            Table(
                Thead(
                    Tr(
                        Th("Rank"),
                        Th("Model"),
                        Th("Profit %"),
                        Th("Max Possible Profit"),
                        Th("Total Profit"),
                        Th("Code Link"),
                    )
                ),
                Tbody(*table_rows),
                cls="table table-striped table-hover",
            ),
        )

    content = []
    if latest:
        content.append(build_table("Latest Session", latest))
    if overall:
        content.append(build_table("All Time", overall))
    if not content:
        content.append(P("No leaderboard data available.", cls="text-center mt-4"))

    return Div(*content, cls="container mt-4")


serve()
