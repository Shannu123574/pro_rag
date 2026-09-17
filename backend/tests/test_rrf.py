from app.retrieval import rrf
class X:
    def __init__(self,id): self.id=id
def test_rrf_fuses_rankings():
    a,b,c=X(1),X(2),X(3)
    assert rrf([a,b],[b,c])[0].id==2
