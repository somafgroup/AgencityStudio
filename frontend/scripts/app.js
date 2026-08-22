import Alpine from 'alpinejs';
import htmx from 'htmx.org';
import {
  createIcons,
  LayoutDashboard,
  FolderKanban,
  Database,
  Activity,
  GitCompareArrows,
  FileText,
  BookOpen,
  FlaskConical,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
  Moon,
  Monitor,
  Info,
  RefreshCw,
  X,
  Building2,
  ChevronsUpDown,
  Plus,
  UserCircle,
  Settings,
  Users,
  LogOut,
  MoreHorizontal,
  Copy,
  Archive,
  ArchiveRestore,
  Trash2,
  History,
} from 'lucide';

window.Alpine = Alpine;
window.htmx = htmx;

const iconSet = {
  LayoutDashboard,
  FolderKanban,
  Database,
  Activity,
  GitCompareArrows,
  FileText,
  BookOpen,
  FlaskConical,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
  Moon,
  Monitor,
  Info,
  RefreshCw,
  X,
  Building2,
  ChevronsUpDown,
  Plus,
  UserCircle,
  Settings,
  Users,
  LogOut,
  MoreHorizontal,
  Copy,
  Archive,
  ArchiveRestore,
  Trash2,
  History,
};

function renderIcons() {
  createIcons({ icons: iconSet, attrs: { 'aria-hidden': 'true', width: 18, height: 18 } });
}

function applyTheme(theme) {
  const allowed = ['light', 'dark', 'system'];
  const value = allowed.includes(theme) ? theme : 'system';
  document.documentElement.dataset.theme = value;
  localStorage.setItem('agencity-theme', value);
  window.dispatchEvent(new CustomEvent('agencity:theme-changed', { detail: { theme: value } }));
  return value;
}

function csrfToken() {
  const entry = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='));
  return entry ? decodeURIComponent(entry.split('=')[1]) : '';
}

async function persistTheme(theme) {
  const endpoint = document.body.dataset.themeEndpoint;
  if (!endpoint) return;
  const body = new URLSearchParams({ theme });
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      'X-CSRFToken': csrfToken(),
    },
    body,
  });
  if (!response.ok) throw new Error('Theme preference could not be saved.');
}

Alpine.data('studioShell', () => ({
  mobileNav: false,
  commandOpen: false,
  commandQuery: '',
  sidebarCollapsed: localStorage.getItem('agencity-sidebar') === 'collapsed',
  theme: localStorage.getItem('agencity-theme') || 'system',
  toasts: [],
  init() {
    applyTheme(this.theme);
    this.$watch('sidebarCollapsed', (value) => {
      localStorage.setItem('agencity-sidebar', value ? 'collapsed' : 'expanded');
    });
    window.addEventListener('studio:toast', (event) => this.pushToast(event.detail || {}));
  },
  async setTheme(theme) {
    this.theme = applyTheme(theme);
    try {
      await persistTheme(this.theme);
      this.pushToast({ type: 'info', message: `Theme set to ${this.theme}.` });
    } catch (_error) {
      this.pushToast({ type: 'error', message: 'Theme changed locally but could not be saved.' });
    }
  },
  toggleCommand() {
    this.commandOpen = !this.commandOpen;
    if (this.commandOpen) {
      this.$nextTick(() => this.$refs.commandInput?.focus());
    }
  },
  closeCommand() {
    this.commandOpen = false;
    this.commandQuery = '';
  },
  matches(label) {
    return !this.commandQuery || label.toLowerCase().includes(this.commandQuery.toLowerCase());
  },
  pushToast({ type = 'info', message = 'Done.' }) {
    const id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    this.toasts.push({ id, type, message });
    if (type !== 'error') {
      setTimeout(() => this.removeToast(id), 5000);
    }
  },
  removeToast(id) {
    this.toasts = this.toasts.filter((toast) => toast.id !== id);
  },
}));

Alpine.start();
renderIcons();

document.body.addEventListener('htmx:afterSwap', renderIcons);
document.body.addEventListener('htmx:responseError', () => {
  window.dispatchEvent(new CustomEvent('studio:toast', {
    detail: { type: 'error', message: 'The requested panel could not be refreshed.' },
  }));
});
