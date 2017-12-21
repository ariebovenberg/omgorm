from dataclasses import dataclass

import snug
from snug.utils import genresult


def test_static(Post):
    recent_posts = snug.query.Fixed(
        request=snug.Request('posts/recent/'),
        load=lambda d: [Post(**o) for o in d])

    assert isinstance(recent_posts, snug.Query)

    resolver = recent_posts.__resolve__()
    assert next(resolver) == snug.Request('posts/recent/')
    assert genresult(resolver, [
        {'id': 4, 'title': 'hello'},
        {'id': 5, 'title': 'goodbye'},
    ]) == [
        Post(4, 'hello'),
        Post(5, 'goodbye'),
    ]


def test_query(Post):

    @dataclass
    class posts(snug.Query):
        count: int

        def __resolve__(self):
            response = yield snug.Request('posts/',
                                          params={'max': self.count})
            return [Post(**d) for d in response]

    query = posts(count=2)
    assert isinstance(query, snug.Query)
    assert query.count == 2

    resolver = query.__resolve__()
    assert next(resolver) == snug.Request('posts/', params={'max': 2})
    assert genresult(resolver, [
        {'id': 4, 'title': 'hello'},
        {'id': 5, 'title': 'goodbye'},
    ]) == [
        Post(4, 'hello'),
        Post(5, 'goodbye'),
    ]


def test_base():

    @dataclass
    class posts(snug.query.Base):
        count: int

        def _request(self):
            return snug.Request('posts/', params={'max': self.count})

    query = posts(count=2)
    assert isinstance(query, snug.Query)
    assert query.count == 2

    resolver = query.__resolve__()
    assert next(resolver) == snug.Request('posts/', params={'max': 2})
    assert genresult(resolver, [
        {'id': 4, 'title': 'hello'},
        {'id': 5, 'title': 'goodbye'},
    ]) == [
        {'id': 4, 'title': 'hello'},
        {'id': 5, 'title': 'goodbye'},
    ]


def test_nestable():

    @dataclass
    class Post:
        id: int

        @dataclass(frozen=True)
        class comments(snug.query.Nestable, snug.Query):
            """comments for this post"""
            post:  'post'
            sort:  bool
            count: int = 15

            def __resolve__(self):
                raise NotImplementedError()

    assert issubclass(Post.comments, snug.Query)

    post34 = Post(id=34)
    post_comments = post34.comments(sort=True)

    assert isinstance(post_comments, snug.Query)
    assert post_comments == Post.comments(post=post34, sort=True)


def test_piped(jsonwrapper, Post):

    @dataclass
    class post(snug.Query):
        id: int

        def __resolve__(self):
            return Post(**(yield snug.Request(
                f'posts/{self.id}/', {'foo': 4})))

    piped = snug.query.Piped(jsonwrapper, post(id=4))

    resolve = piped.__resolve__()
    request = next(resolve)
    assert request == snug.Request('posts/4/', '{"foo": 4}')
    response = genresult(resolve,
                         snug.Response(200, '{"id": 4, "title": "hi"}'))
    assert response == Post(id=4, title='hi')


def test_from_gen(Post):

    @snug.query.from_gen()
    def posts(count: int, search: str='', archived: bool=False):
        """my docstring..."""
        response = yield snug.Request(
            'posts/',
            params={'max': count, 'search': search, 'archived': archived})
        return [Post(**obj) for obj in response]

    assert issubclass(posts, snug.Query)
    assert posts.__name__ == 'posts'
    assert posts.__doc__ == 'my docstring...'
    assert posts.__module__ == 'test_query'
    assert len(posts.__dataclass_fields__) == 3

    my_posts = posts(count=10, search='important')
    assert isinstance(my_posts, snug.Query)
    assert my_posts.count == 10
    assert my_posts.search == 'important'

    resolver = my_posts.__resolve__()
    request = next(resolver)
    assert request == snug.Request(
        'posts/', params={'max': 10,
                          'search': 'important',
                          'archived': False})
    response = genresult(resolver, [
        {'id': 4, 'title': 'hello'},
        {'id': 5, 'title': 'goodbye'},
    ])
    assert response == [
        Post(4, 'hello'),
        Post(5, 'goodbye'),
    ]


class TestFromFunc:

    def test_simple(self, Post):

        @snug.query.from_func(load=lambda l: [Post(**o) for o in l])
        def posts(count: int, search: str='', archived: bool=False):
            """my docstring..."""
            return snug.Request(
                'posts/',
                params={'max': count, 'search': search, 'archived': archived})

        assert posts.__name__ == 'posts'
        assert posts.__doc__ == 'my docstring...'
        assert posts.__module__ == 'test_query'
        assert issubclass(posts, snug.query.Base)
        assert len(posts.__dataclass_fields__) == 3

        my_posts = posts(count=10, search='important')
        assert isinstance(my_posts, snug.Query)
        assert my_posts.count == 10
        assert my_posts.search == 'important'

        assert my_posts._request() == snug.Request(
            'posts/', params={
                'max': 10,
                'search': 'important',
                'archived': False
            })
        assert my_posts._parse([
            {'id': 4, 'title': 'hello'},
            {'id': 5, 'title': 'goodbye'},
        ]) == [
            Post(id=4, title='hello'),
            Post(id=5, title='goodbye'),
        ]
