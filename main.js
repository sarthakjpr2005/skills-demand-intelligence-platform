/**
 * Intelligence Designed To Evolve — Landing Page Interactions
 * 
 * Features:
 * 1. Animated Ease-Out-Cubic Stat Counters with IntersectionObserver
 * 2. Mobile Full-Bleed Navigation Sheet with accessible aria states
 * 3. Video background autoplay assurance
 */

document.addEventListener('DOMContentLoaded', () => {
  /* ═══════════════════════════════════════════════════════════════
     1. STATS COUNT-UP ANIMATION
     easeOutCubic: 1 - Math.pow(1 - t, 3)
     duration: 1500 + i * 80 ms
     start offset: 480 + i * 90 ms
     Triggered once via IntersectionObserver threshold 0.25
     ═══════════════════════════════════════════════════════════════ */

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  const statItems = document.querySelectorAll('.stat-item');
  const statsFooter = document.querySelector('.stats-footer');

  function animateCount(el, target, decimals, duration, delay) {
    const numEl = el.querySelector('.stat-num');
    if (!numEl) return;

    setTimeout(() => {
      let startTime = null;

      function update(currentTime) {
        if (!startTime) startTime = currentTime;
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutCubic(progress);
        const current = target * eased;

        numEl.textContent = current.toFixed(decimals);

        if (progress < 1) {
          requestAnimationFrame(update);
        } else {
          numEl.textContent = target.toFixed(decimals);
        }
      }

      requestAnimationFrame(update);
    }, delay);
  }

  if (statsFooter && statItems.length > 0) {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            statItems.forEach((item, i) => {
              const target = parseFloat(item.getAttribute('data-target')) || 0;
              const decimals = parseInt(item.getAttribute('data-decimals'), 10) || 0;
              const duration = 1500 + i * 80;
              const delay = 480 + i * 90;
              animateCount(item, target, decimals, duration, delay);
            });
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.25 }
    );

    observer.observe(statsFooter);
  }

  /* ═══════════════════════════════════════════════════════════════
     2. MOBILE MENU INTERACTION (≤ 720px)
     - Toggle aria-expanded, hidden, body.menu-open
     - Close on overlay click, Escape key, link click, resize > 720
     ═══════════════════════════════════════════════════════════════ */

  const burgerBtn = document.getElementById('burgerBtn');
  const mobileOverlay = document.getElementById('mobileOverlay');
  const mobileMenu = document.getElementById('mobileMenu');
  const mobileLinks = document.querySelectorAll('.mobile-link, .mobile-signin');

  function openMenu() {
    if (!burgerBtn || !mobileOverlay || !mobileMenu) return;
    burgerBtn.setAttribute('aria-expanded', 'true');
    mobileOverlay.removeAttribute('hidden');
    mobileMenu.removeAttribute('hidden');
    document.body.classList.add('menu-open');
  }

  function closeMenu() {
    if (!burgerBtn || !mobileOverlay || !mobileMenu) return;
    burgerBtn.setAttribute('aria-expanded', 'false');
    mobileOverlay.setAttribute('hidden', '');
    mobileMenu.setAttribute('hidden', '');
    document.body.classList.remove('menu-open');
  }

  function toggleMenu() {
    if (!burgerBtn) return;
    const isExpanded = burgerBtn.getAttribute('aria-expanded') === 'true';
    if (isExpanded) {
      closeMenu();
    } else {
      openMenu();
    }
  }

  if (burgerBtn) {
    burgerBtn.addEventListener('click', toggleMenu);
  }

  if (mobileOverlay) {
    mobileOverlay.addEventListener('click', closeMenu);
  }

  mobileLinks.forEach(link => {
    link.addEventListener('click', () => {
      // Set active link indicator on mobile
      if (link.classList.contains('mobile-link')) {
        mobileLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
      closeMenu();
    });
  });

  // Close on Escape key
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && burgerBtn && burgerBtn.getAttribute('aria-expanded') === 'true') {
      closeMenu();
    }
  });

  // Close on resize > 720px
  window.addEventListener('resize', () => {
    if (window.innerWidth > 720 && burgerBtn && burgerBtn.getAttribute('aria-expanded') === 'true') {
      closeMenu();
    }
  });

  // Desktop nav active indicator interaction
  const desktopLinks = document.querySelectorAll('.nav-link');
  desktopLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      desktopLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');
    });
  });

  /* ═══════════════════════════════════════════════════════════════
     3. BACKGROUND VIDEO AUTOPLAY SAFEGUARD
     ═══════════════════════════════════════════════════════════════ */

  const bgVideo = document.querySelector('.bg-video');
  if (bgVideo) {
    bgVideo.play().catch(() => {
      // Browser autoplay policy might require user interaction or already handled
    });
  }
});
