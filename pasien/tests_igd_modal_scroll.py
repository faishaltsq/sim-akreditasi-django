from html.parser import HTMLParser

from django.urls import reverse
from pasien.tests_asesmen_awal_ux import SmartDefaultUiTest


class ElementTree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = {'tag': 'root', 'attrs': {}, 'children': []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'children': []}
        self.stack[-1]['children'].append(node)
        if tag not in {'input', 'br', 'hr', 'img', 'meta', 'link', 'area', 'source', 'wbr', 'col', 'embed', 'param', 'track', 'base'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                break


def descendants(node):
    yield node
    for child in node['children']:
        yield from descendants(child)


class AssessmentModalStructureTest(SmartDefaultUiTest):
    def test_form_owns_scrollable_modal_sections(self):
        response = self.client.get(reverse('pasien:igd_dashboard'))
        parser = ElementTree()
        parser.feed(response.content.decode())
        modal = next(n for n in descendants(parser.root)
                     if n['attrs'].get('id') == f'modalAsesmenAwal{self.k.pk}')
        forms = [n for n in descendants(modal) if n['tag'] == 'form']
        self.assertEqual(len(forms), 1)
        form = forms[0]
        self.assertIn('modal-content', form['attrs']['class'].split())
        self.assertEqual(form['attrs']['action'], reverse('pasien:igd_asesmen_medis_save', args=[self.k.pk]))
        for section in ('modal-header', 'modal-body', 'modal-footer'):
            self.assertEqual(sum(section in n['attrs'].get('class', '').split() for n in form['children']), 1)
        nodes = list(descendants(form))
        self.assertTrue(any(n['attrs'].get('name') == 'csrfmiddlewaretoken' for n in nodes))
        self.assertEqual(sum(n['attrs'].get('data-bs-toggle') == 'pill' for n in nodes), 7)
        self.assertTrue(any(n['attrs'].get('id') == modal['attrs']['aria-labelledby'] for n in nodes))
        self.assertTrue(any(n['tag'] == 'button' and n['attrs'].get('type') == 'submit' for n in nodes))
