(function () {
  const navToggle = document.querySelector('.nav-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (navToggle && navMenu) {
    navToggle.addEventListener('click', () => {
      const isOpen = navMenu.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', String(isOpen));
    });
  }

  const yearEl = document.getElementById('year');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  const forms = document.querySelectorAll('form[action^="https://formspree.io"]');
  forms.forEach((form) => {
    const status = form.querySelector('.form-status');
    form.addEventListener('submit', async (event) => {
      if (form.dataset.ajax === 'disabled') return;
      event.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      if (status) status.textContent = 'Sending…';
      try {
        const formData = new FormData(form);
        const response = await fetch(form.action, {
          method: 'POST',
          headers: { Accept: 'application/json' },
          body: formData
        });
        if (response.ok) {
          form.reset();
          if (status) {
            status.textContent = 'Thanks! We will reply shortly.';
            status.dataset.state = 'success';
          }
          const track = form.dataset.track;
          if (track) {
            document.dispatchEvent(new CustomEvent('readyfix:track', { detail: { event: track } }));
          }
        } else {
          throw new Error('Network response not ok');
        }
      } catch (error) {
        if (status) {
          status.textContent = 'Something went wrong. Please call us or try again.';
          status.dataset.state = 'error';
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  const mobileCta = document.querySelector('.mobile-cta');
  if (mobileCta) {
    const toggleMobileCta = () => {
      const show = window.scrollY > 200;
      mobileCta.classList.toggle('is-visible', show);
    };
    toggleMobileCta();
    window.addEventListener('scroll', toggleMobileCta, { passive: true });
  }
})();
