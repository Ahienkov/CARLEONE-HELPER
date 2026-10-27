"""Russian-default interface translations; forum documents remain unchanged."""
import re
from string import Formatter

from PySide6.QtWidgets import QApplication, QLabel


LANGUAGES = {'ru': 'Русский', 'uk': 'Українська', 'en': 'English'}
ROWS = [
    ('Блокнот', 'Нотатник', 'Notepad'),
    ('+ Вкладка', '+ Вкладка', '+ Tab'),
    ('Заметка {number}', 'Нотатка {number}', 'Note {number}'),
    ('Вкладки блокнота', 'Вкладки нотатника', 'Notepad tabs'),
    ('Двойной щелчок по вкладке — переименовать', 'Подвійне клацання по вкладці — перейменувати', 'Double-click a tab to rename it'),
    ('Переименовать вкладку', 'Перейменувати вкладку', 'Rename tab'),
    ('Название вкладки', 'Назва вкладки', 'Tab name'),
    ('Удалить вкладку', 'Видалити вкладку', 'Delete tab'),
    ('Удалить вкладку «{title}» и её текст?', 'Видалити вкладку «{title}» та її текст?', 'Delete tab “{title}” and its text?'),
    ('Записывайте сюда всё, что нужно запомнить…', 'Записуйте сюди все, що потрібно запам’ятати…', 'Write down anything you need to remember…'),
    ('Автосохранение на этом компьютере. Общие заметки для всех серверов.',
     'Автозбереження на цьому комп’ютері. Спільні нотатки для всіх серверів.',
     'Autosaved on this computer. Shared notes for all servers.'),
    ('Сохранено на этом компьютере', 'Збережено на цьому комп’ютері', 'Saved on this computer'),
    ('Не удалось прочитать блокнот.', 'Не вдалося прочитати нотатник.', 'Could not read the notepad.'),
    ('Не удалось сохранить блокнот. Текст остаётся в редакторе.',
     'Не вдалося зберегти нотатник. Текст залишається в редакторі.',
     'Could not save the notepad. The text remains in the editor.'),
    ('Общий итог', 'Загальний підсумок', 'Overall total'),
    ('Обе вкладки, выбранный сервер и период. Покупки, расходы и продажи учитываются по датам операций.',
     'Обидві вкладки, вибрані сервер і період. Купівлі, витрати та продажі враховуються за датами операцій.',
     'Both tabs, selected server and period. Purchases, costs and sales use their transaction dates.'),
    ('Двойной щелчок — ввести или изменить цену продажи.',
     'Подвійне клацання — ввести або змінити ціну продажу.',
     'Double-click to enter or change the sale price.'),
    ('Доходы', 'Доходи', 'Income'), ('Перекупство', 'Перепродаж', 'Reselling'),
    ('Учёт покупок, продаж и прибыли', 'Облік купівель, продажів і прибутку', 'Purchases, sales and profit'),
    ('Название товара', 'Назва товару', 'Item name'), ('Товар', 'Товар', 'Item'),
    ('Покупка', 'Купівля', 'Purchase'), ('Продажа', 'Продаж', 'Sale'),
    ('Доп. расходы', 'Дод. витрати', 'Extra costs'), ('Прибыль', 'Прибуток', 'Profit'),
    ('Дата покупки', 'Дата купівлі', 'Purchase date'), ('Статус', 'Статус', 'Status'),
    ('Продано', 'Продано', 'Sold'), ('Не продано', 'Не продано', 'Unsold'),
    ('Отметить продажу', 'Позначити продаж', 'Mark as sold'), ('Цена продажи', 'Ціна продажу', 'Sale price'),
    ('В товаре: {amount}', 'У товарі: {amount}', 'Inventory cost: {amount}'),
    ('Выручка: {amount}', 'Виторг: {amount}', 'Revenue: {amount}'),
    ('Прибыль: {amount}', 'Прибуток: {amount}', 'Profit: {amount}'),
    ('Введите название товара.', 'Введіть назву товару.', 'Enter an item name.'),
    ('Укажите цену покупки больше нуля и корректные расходы.',
     'Укажіть ціну купівлі більшу за нуль і коректні витрати.', 'Enter a positive purchase price and valid costs.'),
    ('Сделка не найдена или товар уже продан.', 'Угоду не знайдено або товар уже продано.',
     'The deal was not found or the item is already sold.'),
    ('Не удалось прочитать сделки. Сохранённые данные не изменены.',
     'Не вдалося прочитати угоди. Збережені дані не змінено.', 'Could not read deals. Saved data has not been changed.'),
    ('Продажа 0 — товар ещё не продан. Прибыль = продажа − покупка − дополнительные расходы.',
     'Продаж 0 — товар ще не продано. Прибуток = продаж − купівля − додаткові витрати.',
     'Sale 0 means unsold. Profit = sale − purchase − extra costs.'),
    ('Период — по дате покупки. Сделки сохраняются отдельно от вкладки «Доходы».',
     'Період — за датою купівлі. Угоди зберігаються окремо від вкладки «Доходи».',
     'The period uses the purchase date. Deals are stored separately from the Income tab.'),
    ('Заработок', 'Заробіток', 'Earnings'),
    ('Среда', 'Середовище', 'Environment'),
    ('Выбрать среду', 'Вибрати середовище', 'Choose environment'),
    ('Учёт доходов и расходов', 'Облік доходів і витрат', 'Income and expense tracker'),
    ('Доход', 'Дохід', 'Income'), ('Расход', 'Витрата', 'Expense'),
    ('Тип операции', 'Тип операції', 'Entry type'), ('Сумма', 'Сума', 'Amount'),
    ('Дата', 'Дата', 'Date'), ('Комментарий', 'Коментар', 'Description'),
    ('Комментарий (необязательно)', 'Коментар (необов’язково)', 'Description (optional)'),
    ('Добавить', 'Додати', 'Add'), ('Удалить запись', 'Видалити запис', 'Delete entry'),
    ('Доходы: {amount}', 'Доходи: {amount}', 'Income: {amount}'),
    ('Расходы: {amount}', 'Витрати: {amount}', 'Expenses: {amount}'),
    ('Баланс: {amount}', 'Баланс: {amount}', 'Balance: {amount}'),
    ('Записи сохраняются только на этом компьютере, отдельно для каждого сервера.',
     'Записи зберігаються лише на цьому комп’ютері, окремо для кожного сервера.',
     'Entries are stored on this computer only, separately for each server.'),
    ('За всё время', 'За весь час', 'All time'), ('Сегодня', 'Сьогодні', 'Today'),
    ('За 7 дней', 'За 7 днів', 'Last 7 days'), ('За 30 дней', 'За 30 днів', 'Last 30 days'),
    ('Текущий месяц', 'Поточний місяць', 'This month'),
    ('Выбрать даты', 'Вибрати дати', 'Custom dates'), ('Период', 'Період', 'Period'),
    ('Дата начала', 'Дата початку', 'Start date'), ('Дата окончания', 'Дата завершення', 'End date'),
    ('Дата начала должна быть не позже даты окончания.', 'Дата початку має бути не пізніше дати завершення.',
     'The start date must not be after the end date.'),
    ('Введите сумму больше нуля.', 'Введіть суму більшу за нуль.', 'Enter an amount greater than zero.'),
    ('Не удалось прочитать записи. Сохранённые данные не изменены.',
     'Не вдалося прочитати записи. Збережені дані не змінено.',
     'Could not read entries. Saved data has not been changed.'),
    ('Не удалось сохранить записи на этом компьютере.', 'Не вдалося зберегти записи на цьому комп’ютері.',
     'Could not save entries on this computer.'),
    ('{key}: активная программа запущена от администратора. Перезапустите помощник от администратора.',
     '{key}: активну програму запущено від адміністратора. Перезапустіть помічник від адміністратора.',
     '{key}: the active program is running as administrator. Restart the helper as administrator.'),
    ('Настройки', 'Налаштування', 'Settings'),
    ('Настройки приложения', 'Налаштування застосунку', 'Application settings'),
    ('Настройки GTA 5 RP HELPER', 'Налаштування GTA 5 RP HELPER', 'GTA 5 RP HELPER settings'),
    ('Язык интерфейса', 'Мова інтерфейсу', 'Interface language'),
    ('Сохранить', 'Зберегти', 'Save'), ('Отмена', 'Скасувати', 'Cancel'),
    ('Сбросить', 'Скинути', 'Reset'), ('Отключить', 'Вимкнути', 'Disable'),
    ('Отключена', 'Вимкнено', 'Disabled'),
    ('Показать / скрыть окно', 'Показати / приховати вікно', 'Show / hide window'),
    ('Поверх других окон', 'Поверх інших вікон', 'Always on top'),
    ('Проверять обновления при запуске', 'Перевіряти оновлення під час запуску', 'Check for updates on startup'),
    ('Непрозрачность фона', 'Непрозорість фону', 'Background opacity'),
    ('Непрозрачность фона: {value}%', 'Непрозорість фону: {value}%', 'Background opacity: {value}%'),
    ('Карточки законов и правил остаются непрозрачными.\nКнопка ↻ проверяет обновления независимо от настройки запуска.',
     'Картки законів і правил залишаються непрозорими.\nКнопка ↻ перевіряє оновлення незалежно від налаштування запуску.',
     'Law and rule cards remain opaque.\nThe ↻ button checks for updates regardless of the startup setting.'),
    ('Тексты законов и правил отображаются в оригинале с форума.', 'Тексти законів і правил відображаються в оригіналі з форуму.', 'Laws and rules are shown in their original forum language.'),
    ('Настройки не применены', 'Налаштування не застосовано', 'Settings were not applied'),
    ('Непрозрачность должна быть от 60 до 100%.', 'Непрозорість має бути від 60 до 100%.', 'Opacity must be between 60 and 100%.'),
    ('Некорректное значение настройки.', 'Некоректне значення налаштування.', 'Invalid setting value.'),
    ('Не удалось сохранить настройки на этом компьютере.', 'Не вдалося зберегти налаштування на цьому комп’ютері.', 'Could not save settings on this computer.'),
    ('Выберите клавишу или сочетание', 'Виберіть клавішу або комбінацію', 'Choose a key or shortcut'),
    ('Выбрать клавишу или сочетание', 'Вибрати клавішу або комбінацію', 'Choose a key or shortcut'),
    ('Нажмите клавишу или сочетание клавиш', 'Натисніть клавішу або комбінацію клавіш', 'Press a key or shortcut'),
    ('Нажмите клавишу или сочетание клавиш.', 'Натисніть клавішу або комбінацію клавіш.', 'Press a key or shortcut.'),
    ('Нажмите, затем нажмите нужную клавишу или сочетание', 'Натисніть, а потім натисніть потрібну клавішу або комбінацію', 'Click, then press the key or shortcut you want'),
    ('Например: H, F4, Ctrl+H или Ctrl+Shift+H.\nНажатая комбинация будет записана автоматически.', 'Наприклад: H, F4, Ctrl+H або Ctrl+Shift+H.\nНатиснуту комбінацію буде записано автоматично.', 'For example: H, F4, Ctrl+H or Ctrl+Shift+H.\nYour shortcut will be recorded automatically.'),
    ('Используйте одно сочетание клавиш, а не последовательность.', 'Використовуйте одну комбінацію клавіш, а не послідовність.', 'Use a single shortcut, not a sequence.'),
    ('Добавьте основную клавишу к Ctrl, Alt, Shift или Win.', 'Додайте основну клавішу до Ctrl, Alt, Shift або Win.', 'Add a main key to Ctrl, Alt, Shift or Win.'),
    ('Эту клавишу нельзя использовать как глобальную. Выберите другую.', 'Цю клавішу не можна використовувати як глобальну. Виберіть іншу.', 'This key cannot be used as a global shortcut. Choose another.'),
    ('Клавиша {key} занята другой программой. Выберите другую.', 'Клавішу {key} використовує інша програма. Виберіть іншу.', 'The shortcut {key} is used by another application. Choose another.'),
    ('Горячая клавиша отключена', 'Гарячу клавішу вимкнено', 'Shortcut disabled'),
    ('{key} — показать / скрыть', '{key} — показати / приховати', '{key} — show / hide'),
    ('{key} занята другой программой', '{key} використовує інша програма', '{key} is used by another application'),
    ('{key} занята другим приложением · Глобальный вызов недоступен', '{key} використовує інший застосунок · Глобальний виклик недоступний', '{key} is in use · Global shortcut unavailable'),
    ('GTA 5 RP HELPER — помощник GTA 5 RP', 'GTA 5 RP HELPER — помічник GTA 5 RP', 'GTA 5 RP HELPER — GTA 5 RP assistant'),
    ('Свернуть', 'Згорнути', 'Collapse'), ('Развернуть / восстановить', 'Розгорнути / відновити', 'Maximize / restore'),
    ('Свернуть окно', 'Згорнути вікно', 'Minimize'),
    ('Закрыть', 'Закрити', 'Close'),
    ('Законы', 'Закони', 'Laws'), ('Правила', 'Правила', 'Rules'),
    ('Поиск по законам', 'Пошук за законами', 'Search laws'), ('Поиск по правилам', 'Пошук за правилами', 'Search rules'),
    ('Все', 'Усі', 'All'), ('Уголовный', 'Кримінальний', 'Criminal'),
    ('Административный', 'Адміністративний', 'Administrative'), ('Дорожный', 'Дорожній', 'Traffic'),
    ('Процессуальный', 'Процесуальний', 'Procedural'), ('Трудовой', 'Трудовий', 'Labor'),
    ('Охота и рыбалка', 'Полювання та риболовля', 'Hunting and fishing'),
    ('Оборот оружия', 'Обіг зброї', 'Weapons'), ('Адвок. Деятельность', 'Адвокатська діяльність', 'Legal practice'),
    ('Общие правила', 'Загальні правила', 'General rules'), ('Госорганизации', 'Держорганізації', 'Government'),
    ('Криминальные', 'Кримінальні', 'Criminal groups'), ('Неофициальные', 'Неофіційні', 'Unofficial groups'),
    ('Криминальные организации', 'Кримінальні організації', 'Criminal organizations'),
    ('Неофициальные организации', 'Неофіційні організації', 'Unofficial organizations'),
    ('Все темы', 'Усі теми', 'All topics'), ('Тема правил', 'Тема правил', 'Rule topic'),
    ('Применить изменения интерфейса и локальных данных', 'Застосувати зміни інтерфейсу та локальних даних', 'Apply interface changes and reload local data'),
    ('Обновить приложение', 'Оновити застосунок', 'Refresh application'),
    ('Ещё', 'Ще', 'More'), ('Ещё: {category}', 'Ще: {category}', 'More: {category}'),
    ('Развернуть остальные разделы законов', 'Розгорнути інші розділи законів', 'Show more law sections'),
    ('Свернуть разделы', 'Згорнути розділи', 'Collapse sections'),
    ('Развернуть остальные разделы', 'Розгорнути інші розділи', 'Show more sections'),
    (' · Выбран раздел: {category}', ' · Вибрано розділ: {category}', ' · Selected section: {category}'),
    ('Показать ещё', 'Показати ще', 'Show more'), ('Показать ещё {count}', 'Показати ще {count}', 'Show {count} more'),
    ('Найдено {noun}: {count} · Показано: {shown}', 'Знайдено {noun}: {count} · Показано: {shown}', '{noun} found: {count} · Shown: {shown}'),
    ('правил', 'правил', 'rules'), ('статей', 'статей', 'articles'),
    ('Ничего не найдено. Измени запрос или выбери «Все».', 'Нічого не знайдено. Змініть запит або виберіть «Усі».', 'Nothing found. Change your search or select All.'),
    ('{section} для сервера {server} ещё не добавлены.', '{section} для сервера {server} ще не додано.', '{section} have not been added for {server} yet.'),
    ('Правила сервера', 'Правила сервера', 'Server rules'), ('Кодексы', 'Кодекси', 'Codes'),
    ('Правило', 'Правило', 'Rule'), ('Справка', 'Довідка', 'Reference'),
    ('Нажми, чтобы скопировать этот блок', 'Натисніть, щоб скопіювати цей блок', 'Click to copy this block'),
    ('Нажми, чтобы скопировать статью', 'Натисніть, щоб скопіювати статтю', 'Click to copy the article'),
    ('Статья {number} — {title}', 'Стаття {number} — {title}', 'Article {number} — {title}'),
    ('{category} · Пункт {number} — {title}', '{category} · Пункт {number} — {title}', '{category} · Rule {number} — {title}'),
    ('✓ Номер статьи скопирован', '✓ Номер статті скопійовано', '✓ Article number copied'),
    ('✓ Заголовок скопирован', '✓ Заголовок скопійовано', '✓ Title copied'),
    ('✓ Описание скопировано', '✓ Опис скопійовано', '✓ Description copied'),
    ('✓ Наказание скопировано', '✓ Покарання скопійовано', '✓ Penalty copied'),
    ('Обновлено', 'Оновлено', 'Updated'), ('Не удалось обновить', 'Не вдалося оновити', 'Refresh failed'),
    ('Не удалось применить изменения:\n{error}', 'Не вдалося застосувати зміни:\n{error}', 'Could not apply changes:\n{error}'),
    ('Форум: ожидание', 'Форум: очікування', 'Forum: waiting'),
    ('Форум: проверка…', 'Форум: перевірка…', 'Forum: checking…'),
    ('Форум: локальная база', 'Форум: локальна база', 'Forum: local database'),
    ('Форум: ошибка проверки', 'Форум: помилка перевірки', 'Forum: check failed'),
    ('Форум: обновлено', 'Форум: оновлено', 'Forum: updated'),
    ('Форум: актуально', 'Форум: актуально', 'Forum: up to date'),
    ('Форум: данные сохранены', 'Форум: дані збережено', 'Forum: data saved'),
    ('Приложение: обновление…', 'Застосунок: оновлення…', 'Application: updating…'),
    ('Обновление загружено', 'Оновлення завантажено', 'Update downloaded'),
    ('Доступна новая сборка', 'Доступна нова збірка', 'New build available'),
    ('Состояние проверки форума', 'Стан перевірки форуму', 'Forum update status'),
    ('Проверка версии GTA 5 RP HELPER', 'Перевірка версії GTA 5 RP HELPER', 'Checking GTA 5 RP HELPER version'),
    ('Проверка форума в фоне: {topic}', 'Фонова перевірка форуму: {topic}', 'Checking the forum: {topic}'),
    ('Форум проверяется при запуске и по кнопке ↻. В остальное время используется локальная база.', 'Форум перевіряється під час запуску та кнопкою ↻. В інший час використовується локальна база.', 'The forum is checked on startup and with ↻. Otherwise, the local database is used.'),
    ('Проверка при запуске отключена. Проверить обновления можно кнопкой ↻.', 'Перевірку під час запуску вимкнено. Перевірити оновлення можна кнопкою ↻.', 'Startup checks are disabled. Use ↻ to check for updates.'),
    ('Проверка завершена. Используется локальная база. Повторная проверка — только при запуске или по кнопке ↻.', 'Перевірку завершено. Використовується локальна база. Наступна перевірка — лише під час запуску або кнопкою ↻.', 'Check complete. Using the local database. Checks run only on startup or with ↻.'),
    ('Используется сохранённая база. Повторить проверку можно кнопкой ↻.\n{error}', 'Використовується збережена база. Повторити перевірку можна кнопкою ↻.\n{error}', 'Using the saved database. Use ↻ to try again.\n{error}'),
    ('Устанавливается версия {version}. Окно откроется автоматически.', 'Встановлюється версія {version}. Вікно відкриється автоматично.', 'Installing version {version}. The window will reopen automatically.'),
    ('Новая версия применится при следующем запуске приложения.', 'Нову версію буде застосовано під час наступного запуску.', 'The update will be applied the next time the application starts.'),
    ('Данные сохранены, но интерфейс не обновлён. Нажмите ↻.\n{error}', 'Дані збережено, але інтерфейс не оновлено. Натисніть ↻.\n{error}', 'Data saved, but the interface could not be refreshed. Click ↻.\n{error}'),
    ('Не удалось проверить новую версию приложения: {error}', 'Не вдалося перевірити нову версію застосунку: {error}', 'Could not check the application version: {error}'),
    ('Версия {version} требует новую сборку: {url}', 'Версія {version} потребує нової збірки: {url}', 'Version {version} requires a new build: {url}'),
]
ROWS.append(('({minutes} мин, {destination})', '({minutes} хв, {destination})', '({minutes} min, {destination})'))
ROWS.extend([
    ('Автор: Lucifer Mentality', 'Автор: Lucifer Mentality', 'Author: Lucifer Mentality'),
    ('Автор: Lucifer Mentality · Версия {version}', 'Автор: Lucifer Mentality · Версія {version}', 'Author: Lucifer Mentality · Version {version}'),
    ('Нарушения игрока ({count})', 'Порушення гравця ({count})', 'Player violations ({count})'),
    ('Показать выбранные нарушения игрока', 'Показати вибрані порушення гравця', 'Show selected player violations'),
    ('Очистить нарушения игрока', 'Очистити порушення гравця', 'Clear player violations'),
    ('Убрать правило из нарушений', 'Прибрати правило з порушень', 'Remove rule from violations'),
    ('Добавить правило в нарушения', 'Додати правило до порушень', 'Add rule to violations'),
    ('Список нарушений пуст. Добавь правила кнопкой «+ В нарушения» в разделе правил.',
     'Список порушень порожній. Додай правила кнопкою «+ До порушень» у розділі правил.',
     'No violations selected. Use “+ Add violation” on a rule in Rules.'),
    ('В разработке', 'У розробці', 'In development'),
    ('Нарушения подозреваемого ({count})', 'Порушення підозрюваного ({count})', 'Suspect violations ({count})'),
    ('Нарушения ({count})', 'Порушення ({count})', 'Violations ({count})'),
    ('Показать выбранные статьи подозреваемого', 'Показати вибрані статті підозрюваного', 'Show the suspect’s selected articles'),
    ('Очистить нарушения подозреваемого', 'Очистити порушення підозрюваного', 'Clear the suspect’s violations'),
    ('+ В нарушения', '+ До порушень', '+ Add violation'),
    ('✓ В списке', '✓ У списку', '✓ Added'),
    ('Убрать статью из нарушений', 'Прибрати статтю з порушень', 'Remove article from violations'),
    ('Добавить статью в нарушения', 'Додати статтю до порушень', 'Add article to violations'),
    ('Список нарушений пуст. Добавь статьи кнопкой «+ В нарушения» в разделе законов.',
     'Список порушень порожній. Додай статті кнопкою «+ До порушень» у розділі законів.',
     'No violations selected. Use “+ Add violation” on an article in Laws.'),
    ('Не удалось сохранить список нарушений.', 'Не вдалося зберегти список порушень.', 'Could not save the violations list.'),
])
CATALOG = {ru: {'ru': ru, 'uk': uk, 'en': en} for ru, uk, en in ROWS}
PATTERNS = []
for source in CATALOG:
    if '{' in source:
        pattern = ''.join(re.escape(text) + (f'(?P<{field}>.*?)' if field else '') for text, field, _, _ in Formatter().parse(source))
        PATTERNS.append((re.compile('^' + pattern + '$', re.DOTALL), source))


def current_language():
    app = QApplication.instance()
    language = app.property('ui_language') if app else None
    return language if language in LANGUAGES else 'ru'


def tr(source, language=None, **values):
    language = language or current_language()
    if language not in LANGUAGES:
        language = 'ru'
    if source in CATALOG:
        translated = CATALOG[source][language]
        return translated.format(**values) if values else translated
    if language != 'ru':
        for pattern, template in PATTERNS:
            match = pattern.fullmatch(source)
            if match:
                return CATALOG[template][language].format(**match.groupdict())
        if '\n' in source:
            return '\n'.join(tr(line, language) for line in source.split('\n'))
    return source.format(**values) if values else source


class LocalizedLabel(QLabel):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self.source_text = ''
        self.source_tooltip = ''
        self.setText(text)

    def setText(self, text):
        self.source_text = text
        super().setText(tr(text))

    def setToolTip(self, text):
        self.source_tooltip = text
        super().setToolTip(tr(text))

    def retranslate(self):
        super().setText(tr(self.source_text))
        super().setToolTip(tr(self.source_tooltip))
