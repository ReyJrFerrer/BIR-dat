'use strict';
const filter = document.querySelector('#issue-filter');
if (filter) {
  filter.addEventListener('change', () => {
    document.querySelectorAll('.issue').forEach(issue => {
      issue.hidden = filter.value !== 'all' && issue.dataset.category !== filter.value;
    });
  });
}
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button');
    if (button) { button.disabled = true; button.textContent = 'Processing…'; }
  });
});
// Reveal collapsed details when an issue link targets an advanced field.
function revealTarget() {
  const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (!target) return;
  let parent = target;
  while (parent) {
    if (parent.tagName === 'DETAILS') parent.open = true;
    parent = parent.parentElement;
  }
  target.scrollIntoView({block: 'start'});
}
window.addEventListener('hashchange', revealTarget);
if (location.hash) revealTarget();
