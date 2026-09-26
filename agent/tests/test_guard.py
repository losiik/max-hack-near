from digital_employee.guard import FALLBACK, AnswerGuard, GuardedReply

guard = AnswerGuard(["Номер из 11 цифр, например 123-456-789 00"])


def say(*chunks):
    reply = GuardedReply(guard)
    spoken = []
    for chunk in chunks:
        spoken += reply.feed(chunk)
    spoken += reply.finish()
    return reply, spoken


def test_plain_explanation_passes():
    assert guard.problem("Выберите «Пенсионер по старости», если получаете пенсию.") is None


def test_long_numbers_are_not_spoken():
    assert guard.problem("Ваш СНИЛС 112-233-445 95, верно?") == "digits"
    assert guard.problem("Введите код 4821 из СМС.") == "digits"


def test_short_numbers_and_public_format_are_fine():
    assert guard.problem("Номер из 11 цифр, например 123-456-789 00.") is None
    assert guard.problem("В семье 3 человека, площадь 54 метра.") is None


def test_asking_for_a_secret_is_rejected():
    assert guard.problem("Продиктуйте, пожалуйста, код из сообщения.") == "asks_secret"
    assert guard.problem("Назовите номер вашей карты.") == "asks_secret"
    assert guard.problem("Скажите мне ваш СНИЛС.") == "asks_secret"


def test_telling_where_to_enter_a_code_is_fine():
    assert guard.problem("Введите код из СМС в поле ниже.") is None


def test_sentences_are_passed_on_as_soon_as_they_end():
    reply = GuardedReply(guard)

    first = reply.feed("Выберите первый ")
    second = reply.feed("вариант. Потом нажмите")
    rest = reply.feed(" «Далее».") + reply.finish()

    assert first == []
    assert second == ["Выберите первый вариант. "]
    assert rest == ["Потом нажмите «Далее»."]
    assert reply.text == "Выберите первый вариант. Потом нажмите «Далее»."


def test_bad_sentence_is_replaced_and_the_rest_is_dropped():
    reply, spoken = say("Поле для кода. ", "Продиктуйте мне код. ", "А потом нажмите «Далее».")

    assert spoken == ["Поле для кода. ", FALLBACK]
    assert reply.rejected
    assert reply.text == f"Поле для кода. {FALLBACK}"


def test_number_split_between_chunks_is_still_caught():
    reply, spoken = say("Ваш номер 112-23", "3-445 95. Всё верно.")

    assert spoken == [FALLBACK]
    assert reply.rejected


def test_long_answer_stops_at_a_sentence_boundary():
    sentence = "Это поле нужно заполнить по документу, который у вас есть на руках. "
    reply, spoken = say(sentence * 10)

    assert 0 < len(spoken) < 10
    assert len(reply.text) <= 200
    assert not reply.rejected


def test_long_first_sentence_is_still_spoken():
    sentence = "Основание — это документ, " + "который подтверждает право на компенсацию, " * 5 + "и всё."

    reply, spoken = say(sentence, " Второе предложение.")

    assert spoken == [sentence]
    assert reply.text == sentence


def test_answer_without_final_punctuation_is_spoken():
    reply, spoken = say("Нажмите «Далее»")

    assert spoken == ["Нажмите «Далее»"]
