(function () {
  // Mobile menu
  const navToggle = document.querySelector('.nav-toggle');
  const nav = document.getElementById('site-nav');
  if (navToggle && nav) {
    navToggle.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', String(isOpen));
    });
  }

  // Submenus (Services / Areas) expand on tap in the mobile menu
  document.querySelectorAll('.submenu-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.has-menu');
      const isOpen = item.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', String(isOpen));
    });
  });

  // Close the mobile menu after following an in-page link such as #contact
  if (nav) {
    nav.addEventListener('click', (e) => {
      const link = e.target.closest('a[href^="#"]');
      if (link && navToggle) {
        nav.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
    });
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
            status.textContent = 'Thanks! We will reply within one business day.';
            status.dataset.state = 'success';
          }
          if (typeof window.gtag === 'function') {
            window.gtag('event', 'generate_lead', { form: 'contact', page: location.pathname });
          }
        } else {
          throw new Error('Network response not ok');
        }
      } catch (error) {
        if (status) {
          status.textContent = 'Something went wrong. Please call or text 647-699-4607.';
          status.dataset.state = 'error';
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });

  // Track call / text taps in Google Analytics
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href^="tel:"], a[href^="sms:"]');
    if (link && typeof window.gtag === 'function') {
      const type = link.getAttribute('href').startsWith('tel:') ? 'call' : 'text';
      window.gtag('event', 'contact_click', { method: type, page: location.pathname });
    }
  });

  const mobileCta = document.querySelector('.mobile-cta');
  if (mobileCta) {
    const toggleMobileCta = () => {
      mobileCta.classList.toggle('is-visible', window.scrollY > 320);
    };
    toggleMobileCta();
    window.addEventListener('scroll', toggleMobileCta, { passive: true });
  }

  // Hide project photos that fail to load (e.g. not uploaded yet) instead of showing broken icons
  const hideMissing = (img) => {
    const target = img.closest('.ba-slider') || img.closest('picture') || img;
    target.classList.add('is-missing');
  };
  document.querySelectorAll('main img').forEach((img) => {
    if (img.complete && img.naturalWidth === 0) {
      hideMissing(img);
    } else {
      img.addEventListener('error', () => hideMissing(img), { once: true });
    }
  });

  // Before/after sliders
  document.querySelectorAll('.ba-slider input[type="range"]').forEach((slider) => {
    const wrapper = slider.closest('.ba-slider');
    const setPos = (value) => wrapper.style.setProperty('--ba-pos', `${value}%`);
    setPos(slider.value);
    slider.addEventListener('input', (e) => setPos(e.target.value));
  });
})();
