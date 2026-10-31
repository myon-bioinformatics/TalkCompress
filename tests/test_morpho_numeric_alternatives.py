import pytest
from MorphoZip import morpho_zip as mz

@pytest.mark.parametrize('word',['or','OR','oder','ODER','ou','OU'])
@pytest.mark.parametrize('left,right',[('3\n ',' 4'),('3 ','\n 4'),('3\n\t','\t\n -4'),('-3 ',' -4'),('3 ',' +4'),('3.5 ',' −4.5'),('3 ',' -.5')])
def test_numeric_alternative_keeps_conjunction(word,left,right):
    output=mz.compress(left+word+right)
    assert word in output
    assert '/' not in output

@pytest.mark.parametrize('text,expected',[('tea or coffee','tea / coffee'),('tea\n or coffee','tea\n/ coffee'),('3 or later','3 / later'),('either or -4','either / -4')])
def test_non_numeric_alternative_keeps_shortening(text,expected):
    assert mz.compress(text)==expected
