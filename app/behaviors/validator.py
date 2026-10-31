import ast
# import multiprocessing

# Excepciones personalizadas para errores de validación de comportamientos
class BehaviorValidationError(Exception):
    pass
class BehaviorSyntaxError(BehaviorValidationError):
    pass
class BehaviorSecurityError(BehaviorValidationError):
    pass
class BehaviorTimeoutError(BehaviorValidationError):
    pass

class BehaviorValidator(ast.NodeVisitor):
    """
    Clase que valida el código de un comportamiento personalizado.
    """
    def visit_Import(self, node):
      raise BehaviorSecurityError(f"Importaciones no permitidas: {ast.dump(node)}")
  
    def visit_ImportFrom(self, node):
        raise BehaviorSecurityError(f"Importaciones desde módulos no permitidas: {ast.dump(node)}")

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
          if node.func.id in ['exec', 'eval', 'open', 'compile', 'input','__import__']:
            raise BehaviorSecurityError(f"Llamada a función no permitida: {node.func.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
            raise BehaviorSecurityError(f"Acceso a __builtins__ no permitido: {ast.dump(node)}")
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in ['__import__', 'eval', 'exec', 'open', 'compile', 'input']:
            raise BehaviorSecurityError(f"Uso de nombre no permitido: {node.id}")
        self.generic_visit(node)

def validate(code: str):
  try:
      tree = ast.parse(code)
      validator = BehaviorValidator()
      validator.visit(tree)
  except SyntaxError as e:
      raise BehaviorSyntaxError(f"Error de sintaxis en el código: {e}") 
