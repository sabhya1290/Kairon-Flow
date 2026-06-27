# Kairon Flow

Kairon Flow is a production-ready, premium full-stack AI-powered productivity manager and workspace. Built with Django, Tailwind CSS, and custom glassmorphic dark mode styling, it delivers an optimized, modern, and fluid user experience for managing tasks, habits, and app integrations.

---

## 🚀 Features Implemented So Far

### 1. 💬 AI Chat Workspace & Onboarding
*   **Onboarding Flow**: A multi-step onboarding wizard for new users to set up their name, professional work roles (Developer, Designer, etc.), primary productivity goals, and preferred working hours.
*   **Starter Workspace Creation**: Auto-populates starter tasks, categories, and custom habits customized to the user's selected role and goals during onboarding.
*   **AI Chat assistant**: An interactive sidebar assistant that processes commands (e.g., `"add task [name]"`, `"status"`, `"help"`) and supports message history clearing.

### 2. 📋 Master Task List & Interactive Filters
*   **List & Grid Views**: Dynamic toggle switch to display tasks in a clean details list or a sleek grid card layout.
*   **Advanced Filtering**: Filter tasks by Priority (High, Medium, Low), Category, or Completion status.
*   **UI Fixes**: 
    *   Resolved filter dropdown overlap issues by adjusting z-index layers.
    *   Optimized right-panel filters in the Chat Workspace to hover/toggle smoothly on mouse interaction.

### 3. 📊 Overhauled Analytics & Interactive Habits
*   **Real computed Analytics**: Replaced mock data with live calculated statistics including Task Completion Rate, total hours saved, active habit tracking counters, and productivity scores.
*   **Habit Tracker Matrix**: A 7-day grid tracking streaks and completions. Clicking any day cell triggers an asynchronous AJAX request to toggle the habit's daily status and update streaks in real-time.
*   **Activity Visualizations**: Rendered CSS-based charts detailing weekly completion trends and priority breakdown donuts.

### 4. ⚙️ Integration Settings & Preferences
*   **Connected Services**: View active calendar sync integrations (Google Calendar, Microsoft Outlook) with custom switches to toggle sync state.
*   **Simulated OAuth Connection**: A glassmorphic modal form that simulates secure third-party authorizations (Google, Outlook) and updates the connected integrations list dynamically.
*   **Personalization Manager**: Update avatar URLs, change goals, customize peak working hours, and adjust daily saved hours directly from the settings panel.

### 5. ❔ Help Center
*   **Standalone Portal**: The Help link in the sidebar footer opens the Help Center (`/help/`) in a **new browser tab** (`target="_blank"`), utilizing a clean full-width layout.
*   **Instant FAQ Filtering**: Search input field that matches query strings against FAQs and collates results in real-time.
*   **Interactive Accordions**: Clean, collapsible FAQ items.
*   **Support Ticket Form**: Submit tickets/feedback to receive instant, local glassmorphic success toast confirmations.

### 6. 🎨 Premium Dark UI & Custom Modals
*   **Material Design 3 Tokens**: Fully customized color scheme, cards, and styling aligned to modern dark glassmorphic design languages.
*   **Glassmorphic Toast Notifications**: A robust global notification helper (`window.showToast(message, type)`) that displays slide-in notifications with progress indicators, completely replacing standard browser alerts.
*   **Delete Confirmation Modals**: Customized confirm prompt modal (`window.showConfirmModal(message, onConfirm)`) used to handle task deletions and service disconnections.

---

## 🛠️ Technology Stack
*   **Backend Framework**: Django (Python 3)
*   **API Layer**: Django REST Framework (DRF)
*   **Database**: SQLite (default developer configuration)
*   **Frontend & Styling**: Tailwind CSS, Google Fonts (Inter, JetBrains Mono), Material Symbols Outlined

---

## 💻 Running the Project Locally

1. **Set Up Python Virtual Environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install django djangorestframework
   ```

3. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

4. **Start Development Server**
   ```bash
   python manage.py runserver
   ```
   Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your web browser.
