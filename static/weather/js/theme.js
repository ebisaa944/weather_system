// Theme Management System

class ThemeManager {
    constructor() {
        this.themes = ['light', 'dark', 'auto'];
        this.currentTheme = localStorage.getItem('theme') || 'auto';
        this.init();
    }
    
    init() {
        this.createThemeToggle();
        this.applyTheme(this.currentTheme);
        this.watchSystemTheme();
    }
    
    createThemeToggle() {
        const toggle = document.querySelector('.theme-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => this.cycleTheme());
        }
    }
    
    applyTheme(theme) {
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Update toggle button state
        this.updateToggleButton(theme);
        
        // Dispatch theme change event
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
        
        // Update meta theme-color for mobile browsers
        this.updateThemeColor(theme);
    }
    
    cycleTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        this.currentTheme = this.themes[nextIndex];
        this.applyTheme(this.currentTheme);
        
        // Animate toggle
        this.animateToggle();
    }
    
    updateToggleButton(theme) {
        const toggle = document.querySelector('.theme-toggle');
        if (!toggle) return;
        
        // Update aria-label
        toggle.setAttribute('aria-label', `Switch to ${this.getNextTheme()} theme`);
        
        // Update icon visibility
        const lightIcon = toggle.querySelector('.theme-icon-light');
        const darkIcon = toggle.querySelector('.theme-icon-dark');
        
        if (lightIcon && darkIcon) {
            if (theme === 'light' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: light)').matches)) {
                lightIcon.style.opacity = '1';
                darkIcon.style.opacity = '0.5';
            } else {
                lightIcon.style.opacity = '0.5';
                darkIcon.style.opacity = '1';
            }
        }
    }
    
    getNextTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        return this.themes[nextIndex];
    }
    
    animateToggle() {
        const toggle = document.querySelector('.theme-toggle');
        if (!toggle) return;
        
        toggle.classList.add('theme-toggle-animate');
        setTimeout(() => {
            toggle.classList.remove('theme-toggle-animate');
        }, 300);
    }
    
    watchSystemTheme() {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (this.currentTheme === 'auto') {
                this.applyTheme('auto');
            }
        });
    }
    
    updateThemeColor(theme) {
        let color;
        if (theme === 'light' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: light)').matches)) {
            color = '#667eea';
        } else {
            color = '#1a202c';
        }
        
        let metaTheme = document.querySelector('meta[name="theme-color"]');
        if (!metaTheme) {
            metaTheme = document.createElement('meta');
            metaTheme.name = 'theme-color';
            document.head.appendChild(metaTheme);
        }
        metaTheme.content = color;
    }
    
    getCurrentTheme() {
        return this.currentTheme;
    }
    
    isDarkMode() {
        if (this.currentTheme === 'dark') return true;
        if (this.currentTheme === 'auto') {
            return window.matchMedia('(prefers-color-scheme: dark)').matches;
        }
        return false;
    }
    
    // CSS Custom Properties helper
    getCssVariable(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }
    
    setCssVariable(name, value) {
        document.documentElement.style.setProperty(name, value);
    }
}

// Initialize theme manager
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});