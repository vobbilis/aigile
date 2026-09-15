from double import double


def test_double():
    positive_result = double(2)
    zero_result = double(0)
    negative_result = double(-3)

    assert positive_result == 4
    assert type(positive_result) is int
    assert zero_result == 0
    assert type(zero_result) is int
    assert negative_result == -6
    assert type(negative_result) is int
