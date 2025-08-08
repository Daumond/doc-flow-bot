from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from app.db.models import Application, ApplicationStatus, QuestionnaireAnswer, Document
from app.db.repository import session_scope
from app.keyboards.common import doc_type_kb
from pathlib import Path
import hashlib

router = Router(name="agent")

QUESTIONS = [
    ("q01", "Собраны ли оригиналы всех паспортов? (да/нет)"),
    ("q02", "Есть ли свежая выписка ЕГРН? (есть/нет)"),
    ("q03", "Есть обременения? (да/нет)"),
    ("q04", "Есть несовершеннолетние собственники? (да/нет)"),
    ("q05", "Есть ли доверенности? (да/нет)"),
    ("q06", "Согласие супруга(ги) требуется? (да/нет)"),
    ("q07", "Прописанные лица остаются? (да/нет)"),
    ("q08", "Маткапитал использовался? (да/нет)"),
    ("q09", "Ипотека участвует? (да/нет)"),
    ("q10", "Есть задолженности по коммуналке? (да/нет)"),
    ("q11", "Все листы договора подписаны? (да/нет)"),
    ("q12", "Согласованы даты протокола? (да/нет)"),
    ("q13", "Пакет по продавцу полный? (да/нет)"),
    ("q14", "Пакет по покупателю полный? (да/нет)"),
    ("q15", "Нотариус требуется? (да/нет)"),
    ("q16", "Есть дополнительные документы? (да/нет)"),
]

class CreateDeal(StatesGroup):
    deal_type = State()
    contract_no = State()
    protocol_date = State()
    address = State()
    object_type = State()
    head_name = State()
    agent_name = State()
    question_index = State()
    uploading = State()
    awaiting_file = State()

@router.message(F.text == "/new")
async def new_application(message: Message, state: FSMContext):
    await state.set_state(CreateDeal.deal_type)
    await message.answer("Тип сделки (Покупка/Продажа/Альтернатива/Юр.услуги):")

@router.message(CreateDeal.deal_type)
async def deal_type_handler(message: Message, state: FSMContext):
    await state.update_data(deal_type=message.text.strip())
    await state.set_state(CreateDeal.contract_no)
    await message.answer("Номер договора (или '-' чтобы пропустить):")

@router.message(CreateDeal.contract_no)
async def contract_no_handler(message: Message, state: FSMContext):
    await state.update_data(contract_no=None if message.text.strip()=="-" else message.text.strip())
    await state.set_state(CreateDeal.protocol_date)
    await message.answer("Дата подачи протокола (YYYY-MM-DD):")

@router.message(CreateDeal.protocol_date)
async def protocol_date_handler(message: Message, state: FSMContext):
    await state.update_data(protocol_date=message.text.strip())
    await state.set_state(CreateDeal.address)
    await message.answer("Адрес объекта:")

@router.message(CreateDeal.address)
async def address_handler(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await state.set_state(CreateDeal.object_type)
    await message.answer("Тип объекта (квартира/комната/доля/ЗУ/дом/апартаменты и т.п.):")

@router.message(CreateDeal.object_type)
async def object_type_handler(message: Message, state: FSMContext):
    await state.update_data(object_type=message.text.strip())
    await state.set_state(CreateDeal.head_name)
    await message.answer("ФИО руководителя:")

@router.message(CreateDeal.head_name)
async def head_name_handler(message: Message, state: FSMContext):
    await state.update_data(head_name=message.text.strip())
    await state.set_state(CreateDeal.agent_name)
    await message.answer("ФИО сотрудника (ваше ФИО):")

@router.message(CreateDeal.agent_name)
async def agent_name_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    # Создаём заявку сразу, чтобы сохранять ответы и файлы в БД по app_id
    with session_scope() as s:
        app = Application(
            deal_type=data["deal_type"],
            contract_no=data.get("contract_no"),
            protocol_date=data.get("protocol_date"),
            address=data.get("address"),
            object_type=data.get("object_type"),
            head_name=data.get("head_name"),
            agent_name=message.text.strip(),
            status=ApplicationStatus.created,
        )
        s.add(app)
        s.flush()  # получаем app.id
        app_id = app.id
    await state.update_data(application_id=app_id)
    await state.update_data(question_index=0)
    await ask_next_question(message, state)

async def ask_next_question(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("question_index", 0)
    if idx >= len(QUESTIONS):
        await state.set_state(CreateDeal.uploading)
        return await message.answer(
            "Анкета завершена. Теперь загрузите документы. Выберите тип:",
            reply_markup=doc_type_kb()
        )
    key, text = QUESTIONS[idx]
    await state.set_state(CreateDeal.question_index)
    await message.answer(f"{idx+1}/16. {text}")

@router.message(CreateDeal.question_index)
async def save_answer_and_next(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("question_index", 0)
    app_id = data["application_id"]
    key, _ = QUESTIONS[idx]
    answer = message.text.strip()
    with session_scope() as s:
        s.add(QuestionnaireAnswer(application_id=app_id, question_key=key, answer_value=answer))
    await state.update_data(question_index=idx+1)
    await ask_next_question(message, state)

# ====== ЗАГРУЗКА ДОКУМЕНТОВ ======

@router.callback_query(F.data.startswith("doc_"))
async def choose_doc_type(cb: CallbackQuery, state: FSMContext):
    if cb.data == "doc_done":
        await cb.message.answer("Загрузка завершена. Заявка готова для передачи РОП.")
        return await cb.answer()
    doc_type = cb.data.replace("doc_", "")
    await state.update_data(current_doc_type=doc_type)
    await state.set_state(CreateDeal.awaiting_file)
    await cb.message.answer(f"Отправьте файл для типа: {doc_type.upper()} (документ или фото)")
    await cb.answer()

@router.message(CreateDeal.awaiting_file, F.document)
async def on_document(message: Message, state: FSMContext):
    await _save_incoming_file(message, state, is_photo=False)

@router.message(CreateDeal.awaiting_file, F.photo)
async def on_photo(message: Message, state: FSMContext):
    await _save_incoming_file(message, state, is_photo=True)

async def _save_incoming_file(message: Message, state: FSMContext, is_photo: bool):
    data = await state.get_data()
    app_id = data["application_id"]
    doc_type = data.get("current_doc_type", "other")

    # Готовим путь
    base = Path("./data") / str(app_id)
    base.mkdir(parents=True, exist_ok=True)

    if is_photo:
        tg_file = message.photo[-1]
        filename = f"{doc_type}_{tg_file.file_unique_id}.jpg"
        dest = base / filename
        await message.bot.download(tg_file, destination=dest)
    else:
        tg_file = message.document
        filename = tg_file.file_name or f"{doc_type}_{tg_file.file_unique_id}.bin"
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

    await message.answer(
        f"Файл сохранён: <code>{filename}</code> Тип: {doc_type.upper()} Ещё выбрать тип:",
        reply_markup=doc_type_kb()
    )
    # остаёмся в состоянии awaiting_file до нового выбора


@router.callback_query(F.data == "doc_done")
async def finish_upload(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    app_id = data.get("application_id")
    if app_id:
        with session_scope() as s:
            app = s.query(Application).get(app_id)
            if app:
                app.status = ApplicationStatus.created
    await state.clear()
    await cb.message.answer("Загрузка завершена ✅. Заявка готова для проверки РОПом.")
    await cb.answer()
