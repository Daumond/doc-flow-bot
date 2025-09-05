from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.models import Application, ApplicationStatus, QuestionnaireAnswer, Document, User, Task, UserRole
from app.db.repository import session_scope
from app.keyboards.common import doc_type_kb, deal_type_kb, object_type_kb, review_kb
from app.services import yandex_disk as ya, notifier
from app.services.notifier import Notifier
from app.services.protocol_filler import fill_protocol
from pathlib import Path
import hashlib
import json
from datetime import datetime
import logging

from app.config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

router = Router(name="agent")

QUESTIONS = [
    ("q01", "Адрес объекта соответствует расположению по карте, соседним домам и квартирам?", ["да", "нет"]),
    ("q02", "Новорожденные дети без регистрации?", ["проживают", "не проживают"]),
    ("q03", "На Объекте незарегистрированная перепланировка?", ["имеется", "отсутствует"]),
    ("q04", "Данные о незарегистрированной  перепланировке в документах БТИ?", ["есть", "нет"]),
    ("q05", "Претензии третьих лиц в отношении прав на Объект?", ["имеются", "отсутствуют"]),
    ("q06", "У собств./польз. есть признаки неадекватного поведения/ псих.заболевания", ["да", "нет"]),
    ("q07", "Задолженность за электроэнергию/коммунальные платежи/капремонт", ["отсутствует", "имеется", "нет данных"]),
    ("q08", "Дом, планируется", ["под снос", "реконструкцию", "не планируется", "не установлено"]),
    ("q09", "Объект перед сделкой занимают", ["собственники", "арендаторы", "физически свободен"]),
    ("q10", "Объект продается", ["по доверенности", "лично собственником"]),
    ("q11", "К моменту сделки на объекте зарегистрировано ___ человек, из них несовершеннолетних ___ (ручной ввод)", []),
    ("q12", "Срок владения Объектом (ручной ввод)", []),
    ("q13", "Является единственным жильем на момент продажи", ["да", "нет"]),
    ("q14", "Заявление о личном участии в сделке", ["было", "не было"]),
    ("q15", "Средства материнского капитала на приобретение Объекта", ["использовались", " не использовались"]),
    ("q16", "Относится ли Объект к объектам культурного наследия", ["да", "нет"])

]

class CreateDeal(StatesGroup):
    deal_type = State()
    contract_no = State()
    protocol_date = State()
    address = State()
    object_type = State()
    head_name = State()
    review = State()
    question_index = State()
    uploading = State()
    awaiting_file = State()
    upload_additional_docs = State()

class EditApplication(StatesGroup):
    select_field = State()
    edit_field = State()
    confirm_save = State()

@router.message(F.text == "/new")
@router.message(F.text == "📝 Новая заявка")
async def new_application(message: Message, state: FSMContext):
    """Start creating a new application"""
    logger.info(f"Starting new application for user {message.from_user.id}")
    try:
        await state.set_state(CreateDeal.deal_type)
        await message.answer("Тип сделки (Покупка/Продажа/Альтернатива/Юр.услуги):", reply_markup=deal_type_kb())
    except Exception as e:
        logger.error(f"Error starting new application: {e}")
        await message.answer("Произошла ошибка при создании заявки. Пожалуйста, попробуйте позже.")

@router.message(CreateDeal.deal_type)
async def deal_type_handler(message: Message, state: FSMContext):
    """Handle deal type selection"""
    logger.debug(f"Deal type selected: {message.text}")
    try:
        await state.update_data(deal_type=message.text.strip())
        await state.set_state(CreateDeal.contract_no)
        await message.answer("Номер договора:", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error(f"Error in deal_type_handler: {e}")
        await message.answer("Ошибка при обработке типа сделки. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.contract_no)
async def contract_no_handler(message: Message, state: FSMContext):
    """Handle contract number input"""
    logger.debug(f"Contract number input: {message.text}")
    try:
        await state.update_data(contract_no=None if message.text.strip()=="-" else message.text.strip())
        await state.set_state(CreateDeal.protocol_date)
        await message.answer("Дата подачи протокола (дд.мм.гггг):")
    except Exception as e:
        logger.error(f"Error in contract_no_handler: {e}")
        await message.answer("Ошибка при обработке номера договора. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.protocol_date)
async def protocol_date_handler(message: Message, state: FSMContext):
    """Handle protocol date input"""
    logger.debug(f"Protocol date input: {message.text}")
    try:
        try:
            date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
            await state.update_data(protocol_date=message.text.strip())
            await state.set_state(CreateDeal.address)
            await message.answer("Адрес объекта:")
        except ValueError:
            logger.warning(f"Неверный формат даты: {message.text.strip()}")
            await message.answer("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
    except Exception as e:
        logger.error(f"Error in protocol_date_handler: {e}")
        await message.answer("Ошибка при обработке даты протокола. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.address)
async def address_handler(message: Message, state: FSMContext):
    """Handle address input"""
    logger.debug(f"Address input: {message.text}")
    try:
        await state.update_data(address=message.text.strip())
        await state.set_state(CreateDeal.object_type)
        await message.answer("Тип объекта (квартира/комната/доля/ЗУ/дом/апартаменты):", reply_markup=object_type_kb())
    except Exception as e:
        logger.error(f"Error in address_handler: {e}")
        await message.answer("Ошибка при обработке адреса. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.object_type)
async def object_type_handler(message: Message, state: FSMContext):
    """Handle object type selection"""
    logger.debug(f"Object type selected: {message.text}")
    try:
        await state.update_data(object_type=message.text.strip())
        await state.set_state(CreateDeal.review)
        data = await state.get_data()
        await message.answer(f"Проверьте правильность введённых данных:"
                             f"\nТип сделки: {data['deal_type']}"
                             f"\nНомер договора: {data['contract_no']}"
                             f"\nДата подачи протокола: {data['protocol_date']}"
                             f"\nАдрес объекта: {data['address']}"
                             f"\nТип объекта: {data['object_type']}",
                             # f"\nФИО руководителя: {data['head_name']}",
                             reply_markup=review_kb())
    except Exception as e:
        logger.error(f"Error in object_type_handler: {e}")
        await message.answer("Ошибка при обработке типа объекта. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.head_name)
async def head_name_handler(message: Message, state: FSMContext):
    """Handle head name input"""
    logger.debug(f"Head name input: {message.text}")

    #except Exception as e:
       # logger.error(f"Error in head_name_handler: {e}")
       # await message.answer("Ошибка при обработке ФИО руководителя. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.review)
async def review_info_handler(message: Message, state: FSMContext):
    """Handle review and agent name input"""
    logger.debug(f"Review and agent name input: {message.text}")
    try:
        if message.text.strip() != "✅":
            await message.answer("Отмена создания заявки", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
        await message.answer(f"Переходим к протоколу...", reply_markup=ReplyKeyboardRemove())
        data = await state.get_data()
        sanitazed_contarct_no = data.get("contract_no").replace("/", ".")
        folder_name = f"{data.get('protocol_date')}-{data.get('deal_type')}-{sanitazed_contarct_no}"
        yadisk_path = ya.create_folder(folder_name)
        # Создаём заявку сразу, чтобы сохранять ответы и файлы в БД по app_id
        with session_scope() as s:
            agent = s.query(User).filter(User.telegram_id == message.from_user.id).first()
            # TODO временный костыль на несколько юзеров

            rop = s.query(User).filter(
                User.role == UserRole.rop,
                User.department_no == agent.department_no,
                User.is_active == True,
                User.is_approved == True
            ).first() or None


            lawyer = s.query(User).filter(
                User.role == UserRole.lawyer,
                User.department_no == agent.department_no,
                User.is_active == True,
                User.is_approved == True
            ).first() or None


            app = Application(
                deal_type=data["deal_type"],
                contract_no=data.get("contract_no"),
                protocol_date=data.get("protocol_date"),
                address=data.get("address"),
                object_type=data.get("object_type"),
                head_name=rop.full_name,
                agent_name=agent.full_name,
                status=ApplicationStatus.created,
                yandex_folder=yadisk_path,
                agent_id=agent.id if agent else None,
                rop_id=rop.id if rop else 1,
                lawyer_id=lawyer.id if lawyer else 1
            )
            s.add(app)
            s.flush()  # получаем app.id
            app_id = app.id
        await state.update_data(application_id=app_id)
        await state.update_data(question_index=0)
        await ask_next_question(message, state)
    except Exception as e:
        logger.error(f"Error in agent_name_handler: {e}")
        await message.answer("Ошибка при обработке. Пожалуйста, попробуйте снова.")

async def ask_next_question(message: Message, state: FSMContext):
    """Ask the next question or proceed to document upload if all questions are done"""
    data = await state.get_data()
    idx = data.get("question_index", 0)
    if idx >= len(QUESTIONS):
        await state.set_state(CreateDeal.uploading)
        # Remove the keyboard by sending a message with ReplyKeyboardRemove
        await message.answer(
            "Протокол заполнен. Теперь загрузите документы.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await message.answer(
            "Выберите тип документа:",
            reply_markup=doc_type_kb()
        )
    key, text, options = QUESTIONS[idx]
    await state.set_state(CreateDeal.question_index)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(f"{idx+1}/{len(QUESTIONS)}. {text}", reply_markup=keyboard)

@router.message(CreateDeal.question_index)
async def save_answer_and_next(message: Message, state: FSMContext):
    """Save the answer and ask the next question"""
    logger.debug(f"Saving answer and asking next question")
    try:
        data = await state.get_data()
        idx = data.get("question_index", 0)
        app_id = data["application_id"]
        key, _, _ = QUESTIONS[idx]
        answer = message.text.strip()
        
        # Special handling for question 11 (two numbers input)
        if key == "q11":
            # Try to split by space or comma
            numbers = answer.replace(',', ' ').split()
            if len(numbers) >= 2 and all(num.isdigit() for num in numbers[:2]):
                total, minors = numbers[:2]
                with session_scope() as s:
                    # Save total registered people
                    s.add(QuestionnaireAnswer(
                        application_id=app_id, 
                        question_key="q11_1",
                        answer_value=total
                    ))
                    # Save number of minors
                    s.add(QuestionnaireAnswer(
                        application_id=app_id, 
                        question_key="q11_2",
                        answer_value=minors
                    ))
            else:
                await message.answer(
                    "Пожалуйста, введите два числа через пробел или запятую: "
                    "общее число зарегистрированных и число несовершеннолетних"
                )
                return
        else:
            # Normal question processing
            with session_scope() as s:
                s.add(QuestionnaireAnswer(
                    application_id=app_id, 
                    question_key=key, 
                    answer_value=answer
                ))
        
        await state.update_data(question_index=idx+1)
        await ask_next_question(message, state)
    except Exception as e:
        logger.error(f"Error in save_answer_and_next: {e}")
        await message.answer("Ошибка при обработке ответов. Пожалуйста, попробуйте снова.")

@router.callback_query(F.data.startswith("doc_"))
async def choose_doc_type(cb: CallbackQuery, state: FSMContext):
    """Handle document type selection"""
    logger.debug(f"Document type selected: {cb.data}")
    try:
        if cb.data == "doc_done":
            await finish_upload(cb, state)
            return
        doc_type = cb.data.replace("doc_", "")
        await state.update_data(current_doc_type=doc_type)
        await state.set_state(CreateDeal.awaiting_file)
        await cb.message.answer(f"Отправьте файл для типа: {doc_type.upper()} (документ или фото)")
        await cb.answer()
    except Exception as e:
        logger.error(f"Error in choose_doc_type: {e}")
        await cb.answer("Ошибка при обработке типа документа. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.awaiting_file, F.document)
async def on_document(message: Message, state: FSMContext):
    """Handle document upload"""
    logger.debug(f"Document uploaded: {message.document}")
    try:
        await _save_incoming_file(message, state, is_photo=False)
    except Exception as e:
        logger.error(f"Error in on_document: {e}")
        await message.answer("Ошибка при обработке документа. Пожалуйста, попробуйте снова.")

@router.message(CreateDeal.awaiting_file, F.photo)
async def on_photo(message: Message, state: FSMContext):
    """Handle photo upload"""
    logger.debug(f"Photo uploaded: {message.photo}")
    try:
        await _save_incoming_file(message, state, is_photo=True)
    except Exception as e:
        logger.error(f"Error in on_photo: {e}")
        await message.answer("Ошибка при обработке фото. Пожалуйста, попробуйте снова.")

async def _save_incoming_file(message: Message, state: FSMContext, is_photo: bool):
    """Save the incoming file"""
    logger.debug(f"Saving incoming file")
    try:
        data = await state.get_data()
        app_id = data["application_id"]
        doc_type = data.get("current_doc_type", "other")

        # Готовим путь
        base = Path("./data") / str(app_id)
        base.mkdir(parents=True, exist_ok=True)

        if is_photo:
            tg_file = message.photo[-1]
            filename = f"{doc_type}.jpg"
            dest = base / filename
            await message.bot.download(tg_file, destination=dest)
        else:
            tg_file = message.document
            filename = tg_file.file_name or f"{doc_type}.bin"
            dest = base / filename
            await message.bot.download(tg_file, destination=dest)

        # Хэш
        sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()

        # В БД
        with session_scope() as s:
            s.add(Document(
                application_id=app_id,
                doc_type=doc_type,
                file_name=str(filename),
                local_path=str(dest),
                sha256=sha256,
            ))
            app = s.query(Application).get(app_id)
            if app and app.yandex_folder:
                ya.upload_file(app.yandex_folder, str(dest), str(filename))

        await message.answer(
            f"Файл сохранён: <code>{filename}</code> Тип: {doc_type.upper()} Ещё выбрать тип:",
            reply_markup=doc_type_kb()
        )
        # остаёмся в состоянии awaiting_file до нового выбора
    except Exception as e:
        logger.error(f"Error in _save_incoming_file: {e}")
        await message.answer("Ошибка при сохранении файла. Пожалуйста, попробуйте снова.")

async def finish_upload(cb: CallbackQuery, state: FSMContext):
    """Handle completion of document upload"""
    logger.info(f"Finishing upload for user {cb.from_user.id}")
    try:
        data = await state.get_data()
        app_id = data.get("application_id")
        public_link = None
        if app_id:
            with session_scope() as s:
                app = s.query(Application).get(app_id)
                if app:
                    app.status = ApplicationStatus.created
                    # Try to get public link if yandex_folder exists
                    if getattr(app, "yandex_folder", None):
                        public_link = ya.get_public_link(app.yandex_folder)
                        # Save the public link in the Application if the field exists
                        if hasattr(app, "yandex_public_url"):
                            app.yandex_public_url = public_link

        template_path = "./templates/protocol_template.docx"
        output_path = f"./data/{app_id}/protocol.docx"

        # Собираем данные
        with session_scope() as s:
            app = s.query(Application).get(app_id)
            answers = s.query(QuestionnaireAnswer).filter_by(application_id=app_id).all()
            data_dict = {
                "deal_type": app.deal_type or "",
                "contract_no": app.contract_no or "",
                "protocol_date": app.protocol_date or "",
                "address": app.address or "",
                "object_type": app.object_type or "",
                "head_name": app.head_name or "",
                "agent_name": app.agent_name or ""
            }
            for ans in answers:
                data_dict[ans.question_key] = ans.answer_value

            fill_protocol(template_path, output_path, data_dict)

        # Загрузка на Яндекс.Диск
            if getattr(app, "yandex_folder", None):
                ya.upload_file(app.yandex_folder, output_path, "protocol.docx")
    except Exception as e:
        logger.error(f"Error in finish_upload: {e}")


    await state.clear()
    msg = "Загрузка завершена ✅. Заявка передана для проверки РОПом."
    if public_link:
        msg += f"\n\nСоздана папка в Яндекс.Диске: {public_link}"
    await cb.message.answer(msg)
    await cb.answer()

@router.message(F.text == "/my_applications")
@router.message(F.text == "📂 Мои заявки")
async def my_applications(message: Message):
    """Show all applications for the current agent"""
    with session_scope() as s:
        # Get current user
        user = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
        if not user:
            return await message.answer("Ошибка: пользователь не найден")
        
        # Get all user's applications
        apps = s.query(Application).filter(Application.agent_id == user.id).order_by(Application.created_at.desc()).all()
        
        if not apps:
            return await message.answer("У вас пока нет заявок. Создайте новую с помощью команды /new")
        
        # Group applications by status
        apps_by_status = {}
        for app in apps:
            status_name = app.status.value
            if status_name not in apps_by_status:
                apps_by_status[status_name] = []
            apps_by_status[status_name].append(app)
        
        # Show applications by status
        for status, status_apps in apps_by_status.items():
            status_text = {
                "CREATED": "📝 На проверке у РОПа",
                "TO_LAWYER": "🔍 На проверке у юриста",
                "RETURNED_ROP": "🔄 Требуются доработки",
                "LAWYER_TASK": "📋 Требуются дополнительные документы",
                "CLOSED": "✅ Закрытые заявки"
            }.get(status, f"{status}")
            
            text = f"*{status_text}* ({len(status_apps)}):\n"
            for app in status_apps:
                text += f"\n#{app.id} - {app.deal_type}"
                if app.address:
                    text += f"\n🏠 {app.address}"
                if app.status == ApplicationStatus.returned_rop and app.rop_id:
                    rop = s.get(User, app.rop_id)
                    text += "\n❗ Возвращена с комментарием"
                elif app.status == ApplicationStatus.lawyer_task:
                    task = s.query(Task).filter(
                        Task.application_id == app.id,
                        Task.status == "open"
                    ).order_by(Task.created_at.desc()).first()
                    if task:
                        text += f"\n📌 Задача: {task.text}"
                text += "\n"
            
            # Create keyboard with actions for each application
            kb = InlineKeyboardBuilder()
            for app in status_apps:
                if app.status == ApplicationStatus.returned_rop:
                    kb.button(text=f"#{app.id} - Доработать", callback_data=f"agent_edit_{app.id}")
                elif app.status == ApplicationStatus.lawyer_task:
                    kb.button(text=f"#{app.id} - Загрузить документы", callback_data=f"agent_upload_{app.id}")
                #else:
                #    kb.button(text=f"#{app.id} - Подробнее", callback_data=f"agent_view_{app.id}")
            
            kb.adjust(1)
            await message.answer(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("agent_edit_"))
async def agent_edit_application(cb: CallbackQuery, state: FSMContext):
    """Start editing a returned application"""
    app_id = int(cb.data.split("_")[-1])
    
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if not app or app.status != ApplicationStatus.returned_rop:
            return await cb.answer("Заявка не найдена или не требует доработки", show_alert=True)
        
        # Store app data in state
        await state.update_data(
            app_id=app_id,
            current_data={
                'deal_type': app.deal_type,
                'contract_no': app.contract_no or 'не указан',
                'protocol_date': app.protocol_date or 'не указана',
                'address': app.address or 'не указан',
                'object_type': app.object_type or 'не указан',
                'head_name': app.head_name or 'не указано',
                'agent_name': app.agent_name or 'не указано'
            }
        )
    
    # Show current application data and available fields to edit
    kb = InlineKeyboardBuilder()
    kb.button(text="Тип сделки", callback_data="edit_deal_type")
    kb.button(text="Номер договора", callback_data="edit_contract_no")
    kb.button(text="Дата протокола", callback_data="edit_protocol_date")
    kb.button(text="Адрес объекта", callback_data="edit_address")
    kb.button(text="Тип объекта", callback_data="edit_object_type")
    kb.button(text="ФИО руководителя", callback_data="edit_head_name")
    kb.button(text="ФИО агента", callback_data="edit_agent_name")
    kb.button(text="✅ Завершить редактирование", callback_data="finish_editing")
    kb.adjust(1)
    
    data = (await state.get_data())['current_data']
    text = (
        f"📝 *Редактирование заявки #{app_id}*\n\n"
        f"*Текущие данные:*\n"
        f"• Тип сделки: {data['deal_type']}\n"
        f"• Номер договора: {data['contract_no']}\n"
        f"• Дата протокола: {data['protocol_date']}\n"
        f"• Адрес: {data['address']}\n"
        f"• Тип объекта: {data['object_type']}\n"
        f"• Руководитель: {data['head_name']}\n"
        f"• Агент: {data['agent_name']}\n\n"
        "Выберите поле для редактирования:"
    )
    
    await cb.message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(EditApplication.select_field)
    await cb.answer()

@router.callback_query(EditApplication.select_field)
async def select_field_to_edit(cb: CallbackQuery, state: FSMContext):
    """Handle field selection for editing"""
    if cb.data == "finish_editing":
        await finish_upload(cb, state)
        return
    
    field_map = {
        "edit_deal_type": ("тип сделки (напр. Покупка/Продажа/Альтернатива)", "deal_type"),
        "edit_contract_no": ("номер договора", "contract_no"),
        "edit_protocol_date": ("дату протокола (ДД.ММ.ГГГГ)", "protocol_date"),
        "edit_address": ("адрес объекта", "address"),
        "edit_object_type": ("тип объекта (квартира/дом/участок и т.д.)", "object_type"),
        "edit_head_name": ("ФИО руководителя", "head_name"),
        "edit_agent_name": ("ФИО агента", "agent_name")
    }
    
    if cb.data not in field_map:
        return await cb.answer("Неизвестное поле для редактирования")
    
    field_prompt, field_name = field_map[cb.data]
    await state.update_data(editing_field=field_name)
    await cb.message.answer(f"Введите новый {field_prompt}:")
    await state.set_state(EditApplication.edit_field)
    await cb.answer()

@router.message(EditApplication.edit_field)
async def save_field_edit(message: Message, state: FSMContext):
    """Save edited field and ask for confirmation"""
    data = await state.get_data()
    field_name = data['editing_field']
    new_value = message.text.strip()
    
    # Update the field in current_data
    current_data = data['current_data']
    current_data[field_name] = new_value
    
    await state.update_data(current_data=current_data)
    
    # Show confirmation
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить изменения", callback_data="save_changes")
    kb.button(text="✏️ Продолжить редактирование", callback_data="continue_editing")
    kb.button(text="❌ Отменить", callback_data="cancel_editing")
    kb.adjust(1)
    
    field_display_names = {
        'deal_type': 'Тип сделки',
        'contract_no': 'Номер договора',
        'protocol_date': 'Дата протокола',
        'address': 'Адрес',
        'object_type': 'Тип объекта',
        'head_name': 'Руководитель',
        'agent_name': 'Агент'
    }
    
    await message.answer(
        f"Вы изменили поле *{field_display_names[field_name]}* на: *{new_value}*\n\n"
        "Сохранить изменения?",
        reply_markup=kb.as_markup()
    )
    await state.set_state(EditApplication.confirm_save)

@router.callback_query(EditApplication.confirm_save)
async def handle_edit_confirmation(cb: CallbackQuery, state: FSMContext):
    """Handle save/continue/cancel actions after editing"""
    if cb.data == "save_changes":
        await save_application_changes(cb, state)
    elif cb.data == "continue_editing":
        await continue_editing(cb, state)
    elif cb.data == "cancel_editing":
        await cancel_editing(cb, state)

async def save_application_changes(cb: CallbackQuery, state: FSMContext):
    """Save all changes to the database"""
    data = await state.get_data()
    app_id = data['app_id']
    current_data = data['current_data']
    
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if app:
            # Update all fields
            app.deal_type = current_data['deal_type']
            app.contract_no = current_data['contract_no'] if current_data['contract_no'] != 'не указан' else None
            app.protocol_date = current_data['protocol_date'] if current_data['protocol_date'] != 'не указана' else None
            app.address = current_data['address'] if current_data['address'] != 'не указан' else None
            app.object_type = current_data['object_type'] if current_data['object_type'] != 'не указан' else None
            app.head_name = current_data['head_name'] if current_data['head_name'] != 'не указано' else None
            app.agent_name = current_data['agent_name'] if current_data['agent_name'] != 'не указано' else None
            
            # Reset status to created for ROP review
            app.status = ApplicationStatus.created
            
            # Clear ROP who returned the application
            app.rop_id = None
    
    await cb.message.answer("✅ Изменения сохранены. Заявка отправлена на повторную проверку РОПу.")
    await state.clear()
    await cb.answer()

async def continue_editing(cb: CallbackQuery, state: FSMContext):
    """Continue editing other fields"""
    data = await state.get_data()
    app_id = data['app_id']
    
    # Reset to select_field state and show the edit menu again
    await state.set_state(EditApplication.select_field)
    
    # Reuse the agent_edit_application function to show the menu
    cb.data = f"agent_edit_{app_id}"
    await agent_edit_application(cb, state)

async def cancel_editing(cb: CallbackQuery, state: FSMContext):
    """Cancel editing and clear state"""
    await state.clear()
    await cb.message.answer("❌ Редактирование отменено.")
    await cb.answer()

@router.callback_query(F.data.startswith("agent_upload_"))
async def agent_upload_docs(cb: CallbackQuery, state: FSMContext):
    """Handle agent uploading additional documents for a task"""
    app_id = int(cb.data.split("_")[-1])
    
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if not app or app.status != ApplicationStatus.lawyer_task:
            return await cb.answer("Заявка не найдена или не требует загрузки документов", show_alert=True)
        
        # Set state for document upload
        await state.update_data(upload_app_id=app_id)
        await state.set_state(CreateDeal.upload_additional_docs)
        
        await cb.message.answer(
            f"Загрузите дополнительные документы для заявки #{app_id}.\n"
            "Вы можете отправить несколько файлов. По окончании нажмите 'Готово'.",
            reply_markup=InlineKeyboardBuilder().button(text="Готово", callback_data="upload_done").as_markup()
        )
    
        await cb.answer()

@router.callback_query(F.data == "upload_done")
async def upload_done(cb: CallbackQuery, state: FSMContext, notifier: Notifier):
    """Handle completion of document upload"""
    data = await state.get_data()
    app_id = data.get("upload_app_id")
    
    if not app_id:
        await state.clear()
        return await cb.answer("Ошибка: не найдена заявка", show_alert=True)
    
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if not app:
            await state.clear()
            return await cb.answer("Ошибка: заявка не найдена", show_alert=True)
        
        # Change status back to lawyer review
        app.status = ApplicationStatus.to_lawyer
        
        # Notify the lawyer
        if app.lawyer_id:
            lawyer = s.get(User, app.lawyer_id)
            if lawyer:
                await notifier.notify_user(
                    lawyer.telegram_id,
                    f"Агент загрузил дополнительные документы для заявки #{app_id}.\n"
                    f"Тип сделки: {app.deal_type}\n"
                    f"Адрес: {app.address}"
                )
    
    await cb.message.answer("✅ Документы загружены и отправлены на проверку юристу")
    await state.clear()
    await cb.answer()

# Add this handler for document uploads
@router.message(F.document | F.photo, CreateDeal.upload_additional_docs)
async def handle_additional_document(message: Message, state: FSMContext):
    """Handle additional document uploads for tasks"""
    data = await state.get_data()
    app_id = data.get("upload_app_id")
    
    if not app_id:
        await state.clear()
        return await message.answer("Ошибка: не найдена заявка")
    
    try:
        # Prepare local directory
        base = Path("./data") / str(app_id) / "additional"
        base.mkdir(parents=True, exist_ok=True)
        
        # Handle document or photo
        if message.document:
            tg_file = message.document
            file_ext = Path(tg_file.file_name).suffix if tg_file.file_name else ".bin"
            filename = f"doc_{int(datetime.datetime.utcnow().timestamp())}{file_ext}"
            dest = base / filename
            await message.bot.download(tg_file, destination=dest)
        elif message.photo:
            tg_file = message.photo[-1]
            filename = f"photo_{int(datetime.datetime.utcnow().timestamp())}.jpg"
            dest = base / filename
            await message.bot.download(tg_file, destination=dest)
        else:
            return await message.answer("Неподдерживаемый тип файла")
        
        # Calculate file hash
        file_bytes = dest.read_bytes()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        # Save to database and upload to Yandex.Disk
        with session_scope() as s:
            app = s.query(Application).get(app_id)
            if not app:
                return await message.answer("Ошибка: заявка не найдена")
            
            # Create document record
            doc = Document(
                application_id=app_id,
                doc_type="additional",
                file_name=filename,
                local_path=str(dest),
                yandex_path=f"{app.yandex_folder}/additional/{filename}" if app.yandex_folder else None,
                sha256=sha256,
                meta=json.dumps({
                    "original_name": getattr(message.document, 'file_name', None) or "photo",
                    "mime_type": getattr(message.document, 'mime_type', 'image/jpeg' if message.photo else 'application/octet-stream'),
                    "file_size": len(file_bytes),
                    "uploaded_at": datetime.datetime.utcnow().isoformat()
                })
            )
            s.add(doc)
            s.flush()  # Get the document ID
            
            # Upload to Yandex.Disk if folder is set
            if app.yandex_folder:
                try:
                    remote_path = f"{app.yandex_folder}/additional/{filename}"
                    ya.upload_file(app.yandex_folder, str(dest), f"{filename}")
                    doc.yandex_path = remote_path
                except Exception as e:
                    logger.error(f"Failed to upload to Yandex.Disk: {str(e)}")
        
        await message.answer(f"✅ Файл успешно загружен: {filename}")
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        await message.answer("Произошла ошибка при обработке файла. Пожалуйста, попробуйте снова.")
