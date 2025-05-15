from .api import OdooAPI
import pandas as pd


class OdooAccountability(OdooAPI):
    
    def __init__(self, database='productive'):
        super().__init__(database=database)

    def read_account_balance(self, account_number):
        """
        Lee el saldo actual de una cuenta contable basado en su número.
        
        :param account_number: Número de la cuenta contable
        :return: Dictionary con la información de la cuenta y su saldo, o mensaje de error
        """
        try:
            # Primero, obtener el ID de la cuenta
            account = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'search_read',
                [[['code', '=', str(account_number)]]], 
                {'fields': ['id', 'name', 'code']}
            )

            if not account:
                return f"No se encontró la cuenta con número {account_number}"

            # Luego, obtener el saldo de account.move.line
            domain = [
                ('account_id', '=', account[0]['id']),
                ('parent_state', '=', 'posted')  # Solo movimientos contabilizados
            ]
            
            balance = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move.line', 'read_group',
                [domain],
                {'fields': ['balance'], 'groupby': ['account_id']}
            )

            # Combinar la información
            result = account[0]
            result['balance'] = balance[0]['balance'] if balance else 0.0
            return result

        except Exception as e:
            return f"Error al leer el saldo de la cuenta: {str(e)}"

    def create_account(self, account_data):
        """
        Crea una nueva cuenta contable.
        
        :param account_data: Dictionary con los datos de la cuenta
        :return: ID de la cuenta creada o mensaje de error
        """
        try:
            if self.account_exists(account_data.get('code')):
                return f"La cuenta {account_data.get('code')} ya existe"

            account_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'create',
                [account_data]
            )
            return f"Cuenta creada con ID: {account_id}"

        except Exception as e:
            return f"Error al crear la cuenta: {str(e)}"

    def update_account(self, account_number, account_data):
        """
        Actualiza una cuenta contable existente.
        
        :param account_number: Número de la cuenta a actualizar
        :param account_data: Dictionary con los datos a actualizar
        :return: Mensaje de éxito o error
        """
        try:
            account_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'search',
                [[['code', '=', str(account_number)]]]
            )

            if not account_ids:
                return f"No se encontró la cuenta {account_number}"

            self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'write',
                [account_ids[0], account_data]
            )
            return "Cuenta actualizada exitosamente"

        except Exception as e:
            return f"Error al actualizar la cuenta: {str(e)}"

    def delete_account(self, account_number):
        """
        Elimina una cuenta contable (si está permitido por el sistema).
        
        :param account_number: Número de la cuenta a eliminar
        :return: Mensaje de éxito o error
        """
        try:
            account_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'search',
                [[['code', '=', str(account_number)]]]
            )

            if not account_ids:
                return f"No se encontró la cuenta {account_number}"

            self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'unlink',
                [account_ids[0]]
            )
            return "Cuenta eliminada exitosamente"

        except Exception as e:
            return f"Error al eliminar la cuenta: {str(e)}"
