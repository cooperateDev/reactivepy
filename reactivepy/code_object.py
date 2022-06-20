from symtable import symtable, Symbol
import symtable as symt
import builtins as builtins_mod
from typing import List, FrozenSet
from io import StringIO
from hashlib import blake2b
from .user_namespace import BuiltInManager


ESCAPE_TABLE = str.maketrans({'\a': r'\a',
                              '\b': r'\b',
                              '\f': r'\f',
                              '\n': r'\n',
                              '\r': r'\r',
                              '\t': r'\t',
                              '\v': r'\v',
                              '\'': r'\'',
                              '\"': r'\"'})


class CodeObject:

    @staticmethod
    def describe_symbol(sym):
        output = StringIO()
        assert isinstance(sym, symt.Symbol)

        print(f"Symbol: {sym.get_name()}",  file=output)


        for prop in [
                'referenced', 'imported', 'parameter',
                'global', 'declared_global', 'local',
                'free', 'assigned', 'namespace']:
            if getattr(sym, 'is_' + prop)():
                print(f'    is {prop}', file=output)

        return output.getvalue()

    @staticmethod
    def describe_symtable(st, recursive=True, indent=0, output=StringIO()):
        def print_d(s, *args, **kwargs):
            prefix = ' ' * indent
            print(f"{prefix}{s} {*args} {**kwargs}")

        assert isinstance(st, symt.SymbolTable)
        print_d(f'Symtable: type={st.get_type()}, id={st.get_id()}, name={st.get_name()}', file=output)
        print_d(f'  nested: {st.is_nested()}', file=output)
        print_d(f'  has children:{st.has_children()}', file=output)
        print_d(f'  identifiers: {list(st.get_identifiers())}', file=output)

        if recursive:
            for child_st in st.get_children():
                CodeObject.describe_symtable(
                    child_st, recursive, indent + 5, output=output)

        return output.getvalue()

    @staticmethod
    def _find_input_variables(st, ns_manager: BuiltInManager):
        imports = set()
        return list(CodeObject._find_symbol_tables(st, imports, ns_manager))

    @staticmethod
    def _find_symbol_tables(symbols, imports, ns_manager: BuiltInManager):
        for sym in symbols.get_symbols():
            if sym.is_imported():
                imports.add(sym.get_name())

            # and sym.get_name() != 'show_graph'

            if sym.is_global() and not sym.get_name() in ns_manager and not sym.get_name() in imports:
                yield SymbolWrapper(sym)

        for a in symbols.get_children():
            yield from CodeObject._find_symbol_tables(a, imports, ns_manager)

    @staticmethod
    def _find_output_variables(st):
        # return one top level defined variable, only including support for one
        # as of now
        output_vars = [SymbolWrapper(sym) for sym in st.get_symbols()
                       if sym.is_assigned() or sym.is_imported()]

        num_imports = sum(map(lambda sym: int(sym.is_imported()), output_vars))

        if (len(output_vars) - num_imports) > 1:
            raise MultipleDefinitionsError()
        else:
            return frozenset(output_vars)

    def __init__(self, code: str, key: bytes, ns_manager: BuiltInManager):
        self.symbol_table: symtable = symtable(code, '<string>', 'exec')
        self.code: str = code
        self.input_vars: List[SymbolWrapper] = CodeObject._find_input_variables(self.symbol_table, ns_manager
                                                                                )
        self.output_vars: FrozenSet[SymbolWrapper] = CodeObject._find_output_variables(self.symbol_table
                                                                                       )

        h = blake2b(digest_size=10, key=key)
        if len(self.output_vars) > 0:
            display_id_prefix = "+".join(map(str, self.output_vars))
            h.update(display_id_prefix.encode('utf-8'))
            self.display_id = f"{display_id_prefix}-{h.hexdigest()}"
        else:
            h.update(self.code.encode('utf-8'))
            self.display_id = f"{h.hexdigest()}"

    def __hash__(self):
        return hash(self.display_id)

    def __eq__(self, other):
        if isinstance(other, CodeObject):
            return self.display_id == other.display_id
        return False

    def __repr__(self):
        return f"<Code in:{str(self.input_vars)} out:{str(list(self.output_vars))} code:\"{self.code.translate(ESCAPE_TABLE)}\">"


class SymbolWrapper:
    """Wrapper for symtable Symbols that performs hashing and equality check by name"""

    def __init__(self, symbol: Symbol):
        self._symbol: Symbol = symbol

    def __getattr__(self, attr):
        return self._symbol.__getattribute__(attr)

    def __eq__(self, other):
        if isinstance(other, SymbolWrapper):
            return self._symbol.get_name() == other.get_name()
        return False

    def __hash__(self):
        return hash(self._symbol.get_name())

    def __repr__(self):
        return f'[{self._symbol.get_name()}]'


class MultipleDefinitionsError(Exception):
    """ Attempted to define more than one local variable
    """
    pass
