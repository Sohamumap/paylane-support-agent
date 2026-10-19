import pytest

from paylane.redact import redact


@pytest.mark.parametrize("separator", ["", " ", "-", ".", "\t", "\n", "\u00a0", "\u2011", "\u200b"])
def test_common_card_number_separators_are_hidden(separator):
    number = separator.join(["4111", "1111", "1111", "1111"])
    clean, hidden = redact(f"Card: {number}; do not repeat it.")
    assert clean == "Card: [card number hidden]; do not repeat it."
    assert hidden == ["card number"]


def test_transaction_ids_amounts_and_last_four_are_preserved():
    text = "txn_1001: $42.50; card ending 4821; ticket TCK-0001"
    assert redact(text) == (text, [])


def test_internal_tickets_keep_email_but_remove_grouped_card_numbers():
    clean, hidden = redact("maya.patel@example.com gave 4111.1111.1111.1111", emails=False)
    assert "maya.patel@example.com" in clean
    assert "4111" not in clean
    assert hidden == ["card number"]
