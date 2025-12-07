/**
 * F2 Commander Website - Main JavaScript
 */

(function() {
    'use strict';

    // ===========================
    // Mobile Navigation Toggle
    // ===========================

    function initMobileMenu() {
        const burger = document.querySelector('.navbar-burger');
        const menu = document.querySelector('.navbar-menu');

        if (burger && menu) {
            burger.addEventListener('click', () => {
                burger.classList.toggle('is-active');
                menu.classList.toggle('is-active');

                // Update ARIA attributes for accessibility
                const expanded = burger.classList.contains('is-active');
                burger.setAttribute('aria-expanded', expanded);
            });

            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!burger.contains(e.target) && !menu.contains(e.target)) {
                    burger.classList.remove('is-active');
                    menu.classList.remove('is-active');
                    burger.setAttribute('aria-expanded', 'false');
                }
            });

            // Close menu when clicking on a link
            const menuLinks = menu.querySelectorAll('.navbar-item');
            menuLinks.forEach(link => {
                link.addEventListener('click', () => {
                    burger.classList.remove('is-active');
                    menu.classList.remove('is-active');
                    burger.setAttribute('aria-expanded', 'false');
                });
            });
        }
    }

    // ===========================
    // Smooth Scrolling for Anchor Links
    // ===========================

    function initSmoothScrolling() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const href = this.getAttribute('href');

                // Ignore # without target
                if (href === '#') {
                    return;
                }

                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });

                    // Update URL without jumping
                    if (history.pushState) {
                        history.pushState(null, null, href);
                    }
                }
            });
        });
    }

    // ===========================
    // Copy Code Button for Code Blocks
    // ===========================

    function initCopyButtons() {
        document.querySelectorAll('pre code').forEach(block => {
            const pre = block.parentElement;

            // Don't add button if it already exists or if pre has no-copy class
            if (pre.querySelector('.copy-button') || pre.classList.contains('no-copy')) {
                return;
            }

            const button = document.createElement('button');
            button.className = 'copy-button';
            button.textContent = 'Copy';
            button.setAttribute('aria-label', 'Copy code to clipboard');

            button.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(block.textContent);
                    button.textContent = 'Copied!';
                    button.setAttribute('aria-label', 'Code copied to clipboard');

                    setTimeout(() => {
                        button.textContent = 'Copy';
                        button.setAttribute('aria-label', 'Copy code to clipboard');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy code:', err);
                    button.textContent = 'Error';

                    setTimeout(() => {
                        button.textContent = 'Copy';
                    }, 2000);
                }
            });

            pre.style.position = 'relative';
            pre.appendChild(button);
        });
    }

    // ===========================
    // Image Lightbox for Screenshots
    // ===========================

    function initLightbox() {
        document.querySelectorAll('.screenshot, .screenshot-item img').forEach(img => {
            img.style.cursor = 'pointer';

            img.addEventListener('click', () => {
                // Create lightbox container
                const lightbox = document.createElement('div');
                lightbox.className = 'lightbox';
                lightbox.setAttribute('role', 'dialog');
                lightbox.setAttribute('aria-label', 'Image preview');
                lightbox.setAttribute('aria-modal', 'true');

                // Create image
                const imgElement = document.createElement('img');
                imgElement.src = img.src;
                imgElement.alt = img.alt || 'Screenshot';

                lightbox.appendChild(imgElement);

                // Close on click
                lightbox.addEventListener('click', () => {
                    lightbox.remove();
                    document.body.style.overflow = '';
                });

                // Close on Escape key
                const closeOnEscape = (e) => {
                    if (e.key === 'Escape') {
                        lightbox.remove();
                        document.body.style.overflow = '';
                        document.removeEventListener('keydown', closeOnEscape);
                    }
                };
                document.addEventListener('keydown', closeOnEscape);

                // Prevent body scroll
                document.body.style.overflow = 'hidden';

                // Add to DOM
                document.body.appendChild(lightbox);

                // Focus lightbox for accessibility
                lightbox.focus();
            });
        });
    }

    // ===========================
    // Scroll to Top Button
    // ===========================

    function initScrollToTop() {
        // Create scroll-to-top button
        const scrollBtn = document.createElement('button');
        scrollBtn.className = 'scroll-to-top';
        scrollBtn.innerHTML = '<i class="fas fa-arrow-up"></i>';
        scrollBtn.setAttribute('aria-label', 'Scroll to top');
        scrollBtn.style.display = 'none';

        document.body.appendChild(scrollBtn);

        // Show/hide button based on scroll position
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                if (window.scrollY > 300) {
                    scrollBtn.style.display = 'flex';
                } else {
                    scrollBtn.style.display = 'none';
                }
            }, 100);
        });

        // Scroll to top on click
        scrollBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // ===========================
    // Highlight Active Navigation Item
    // ===========================

    function highlightActiveNavItem() {
        const currentPath = window.location.pathname;
        const navItems = document.querySelectorAll('.navbar-item');

        navItems.forEach(item => {
            const href = item.getAttribute('href');
            if (href && currentPath.includes(href) && href !== '/') {
                item.classList.add('active');
                item.setAttribute('aria-current', 'page');
            } else if (href === '/' && (currentPath === '/' || currentPath === '/index.html')) {
                item.classList.add('active');
                item.setAttribute('aria-current', 'page');
            }
        });
    }

    // ===========================
    // Table of Contents Generator (for docs page)
    // ===========================

    function generateTableOfContents() {
        const tocContainer = document.querySelector('#table-of-contents');
        if (!tocContainer) return;

        const content = document.querySelector('.docs-content');
        if (!content) return;

        const headings = content.querySelectorAll('h2, h3');
        if (headings.length === 0) return;

        const tocList = document.createElement('ul');
        tocList.className = 'docs-nav';

        headings.forEach((heading, index) => {
            // Add ID to heading if it doesn't have one
            if (!heading.id) {
                heading.id = `section-${index}`;
            }

            const listItem = document.createElement('li');
            const link = document.createElement('a');
            link.href = `#${heading.id}`;
            link.textContent = heading.textContent;

            // Indent h3 items
            if (heading.tagName === 'H3') {
                listItem.style.paddingLeft = '1rem';
            }

            listItem.appendChild(link);
            tocList.appendChild(listItem);
        });

        tocContainer.appendChild(tocList);

        // Highlight active section on scroll
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                let currentSection = '';
                headings.forEach(heading => {
                    const rect = heading.getBoundingClientRect();
                    if (rect.top <= 100) {
                        currentSection = heading.id;
                    }
                });

                tocList.querySelectorAll('a').forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${currentSection}`) {
                        link.classList.add('active');
                    }
                });
            }, 100);
        });
    }

    // ===========================
    // Lazy Loading Images
    // ===========================

    function initLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            observer.unobserve(img);
                        }
                    }
                });
            });

            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        } else {
            // Fallback for browsers that don't support IntersectionObserver
            document.querySelectorAll('img[data-src]').forEach(img => {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            });
        }
    }

    // ===========================
    // External Links - Open in New Tab
    // ===========================

    function initExternalLinks() {
        document.querySelectorAll('a[href^="http"]').forEach(link => {
            // Don't modify if already has target
            if (!link.hasAttribute('target')) {
                link.setAttribute('target', '_blank');
                link.setAttribute('rel', 'noopener noreferrer');

                // Add icon for external links (optional)
                // Uncomment if you want visual indicator
                /*
                const icon = document.createElement('i');
                icon.className = 'fas fa-external-link-alt';
                icon.style.marginLeft = '0.25rem';
                icon.style.fontSize = '0.75em';
                link.appendChild(icon);
                */
            }
        });
    }

    // ===========================
    // Keyboard Navigation Enhancement
    // ===========================

    function initKeyboardNav() {
        // Add keyboard navigation for cards
        document.querySelectorAll('.card, .feature-card').forEach(card => {
            if (card.querySelector('a')) {
                card.setAttribute('tabindex', '0');
                card.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        const link = card.querySelector('a');
                        if (link) link.click();
                    }
                });
            }
        });
    }

    // ===========================
    // Initialize All Features
    // ===========================

    function init() {
        // Wait for DOM to be fully loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        // Initialize all features
        initMobileMenu();
        initSmoothScrolling();
        initCopyButtons();
        initLightbox();
        initScrollToTop();
        highlightActiveNavItem();
        generateTableOfContents();
        initLazyLoading();
        initExternalLinks();
        initKeyboardNav();

        // Log initialization (remove in production)
        console.log('F2 Commander website initialized');
    }

    // Start initialization
    init();

})();
