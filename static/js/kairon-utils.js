// CSRF helpers
function getCookie(name) {
    let v = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(c => {
            c = c.trim();
            if (c.substring(0, name.length + 1) === (name + '='))
                v = decodeURIComponent(c.substring(name.length + 1));
        });
    }
    return v;
}

function getCsrfToken() {
    const t = document.querySelector('[name=csrfmiddlewaretoken]');
    return t ? t.value : getCookie('csrftoken');
}

// HTML escape
function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag =>
        ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[tag] || tag));
}

// Text-safe render (escapes HTML then converts \n to <br>)
function renderTextSafe(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML.replace(/\n/g, '<br>');
}
