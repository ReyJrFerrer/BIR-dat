'use strict';

(async () => {
  const key = 'alphalist-review-session-v1';
  const path = `${location.pathname}${location.search}`;
  try {
    const response = await fetch('/browser/page', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path, state: sessionStorage.getItem(key)}),
    });
    if (response.status === 404 && path !== '/') {
      sessionStorage.removeItem(key);
      location.replace('/');
      return;
    }
    if (!response.ok) throw new Error('The review could not be opened. Reload this page to try again.');
    const data = await response.json();
    sessionStorage.setItem(key, data.state);
    document.open();
    document.write(data.html);
    document.close();
  } catch (error) {
    document.querySelector('main').textContent = error.message;
  }
})();
