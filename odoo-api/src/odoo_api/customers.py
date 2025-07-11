from datetime import datetime
from .api import OdooAPI
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class OdooCustomers(OdooAPI):
    
    def __init__(self, db=None, url=None, username=None, password=None):
        super().__init__(db=db, url=url, username=username, password=password)

#---------------------------------AUX---------------------------------
    def _normalize_phone_number_chile(self, phone_number):
        """
        Normaliza un número de teléfono chileno a un formato estándar.
        
        Args:
            phone_number (str): Número de teléfono en diversos formatos.
        
        Returns:
            str: Número normalizado en formato 569XXXXXXXX o None si no es válido.
        """
        if not phone_number:
            return None
            
        digits = ''.join(filter(str.isdigit, str(phone_number)))
        
        if not digits:
            return None
        
        if len(digits) <= 8:
            return f"569{digits}"
        elif len(digits) == 9:
            if digits.startswith('9'):
                return f"56{digits}"
            else:
                logger.warning(f"<_normalize_phone_number_chile> Formato no reconocido: {phone_number}")
                return digits # Devolver tal cual si no es celular
        elif len(digits) >= 10:
            if digits.startswith('56'):
                # Asegurar que tenga el formato 569XXXXXXXX
                if len(digits) == 11 and digits.startswith('569'):
                    return digits
                elif len(digits) == 10 and digits.startswith('56') and digits[2] == '9': # Caso 569XXXXXXX
                    return digits
                elif len(digits) > 11 and digits.startswith('569'): # Podría tener prefijos extras
                    return digits[-11:] # Tomar los últimos 11
                else: # Otros casos con 56X..
                    logger.warning(f"<_normalize_phone_number_chile> Formato con 56 no reconocido: {phone_number}, se usarán los últimos 9 dígitos.")
                    last_nine = digits[-9:]
                    return f"56{last_nine}"
            else:
                # Tomar los últimos 9 dígitos y asumir que es celular
                last_nine = digits[-9:]
                if last_nine.startswith('9'):
                     return f"56{last_nine}"
                else:
                    logger.warning(f"<_normalize_phone_number_chile> Número largo sin 56 no reconocido como celular: {phone_number}")
                    return digits # Devolver tal cual
        
        return digits # Fallback

#---------------------------------CRUD---------------------------------
    def create_customer(self, name: str, phone: Optional[str] = None, email: Optional[str] = None, 
                      vat: Optional[str] = None, street: Optional[str] = None, city: Optional[str] = None) -> Optional[int]:
        """
        Crea un nuevo contacto de cliente en Odoo.
        
        Args:
            name (str): Nombre completo del cliente (requerido).
            phone (str, optional): Número de teléfono.
            email (str, optional): Correo electrónico.
            vat (str, optional): RUT o identificación fiscal.
            street (str, optional): Dirección.
            city (str, optional): Ciudad.
            
        Returns:
            Optional[int]: El ID del cliente creado en Odoo, o None si falla la creación.
        """
        logger.info(f"<create_customer> Intentando crear cliente: {name}")
        try:
            contact_data = {
                'name': name,
                'customer_rank': 1,  # Marcar como cliente
                'company_type': 'person'  # Asumir persona por defecto
            }
            
            # Añadir campos opcionales si se proporcionan
            if phone:
                # Intentar normalizar el teléfono antes de guardarlo
                normalized_phone = self._normalize_phone_number_chile(phone)
                contact_data['phone'] = normalized_phone if normalized_phone else phone
            if email:
                contact_data['email'] = email
            if vat:
                contact_data['vat'] = vat
            if street:
                contact_data['street'] = street
            if city:
                contact_data['city'] = city

            logger.debug(f"<create_customer> Datos a enviar a Odoo: {contact_data}")

            contact_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'create',
                [contact_data]
            )
            
            if contact_id:
                logger.info(f"<create_customer> Cliente '{name}' creado con éxito. ID: {contact_id}")
                return contact_id
            else:
                logger.error(f"<create_customer> La API de Odoo no devolvió un ID para el cliente '{name}'.")
                return None
        
        except Exception as e:
            logger.error(f"<create_customer> Error al crear cliente '{name}' en Odoo: {str(e)}")
            return None

    def read_customer_by_id(self, id):
        """
        Lee un cliente específico por su ID
        
        :param id: ID del cliente
        :return: DataFrame con los datos del cliente o mensaje de error
        """
        try:
            fields = [
                'name',
                'vat',  # RUT o identificación fiscal
                'email',
                'phone',
                'mobile',
                'street',
                'city',
                'state_id',
                'country_id',
                'company_type',  # persona o empresa
                'l10n_latam_identification_type_id',  # tipo de documento
                'create_date',
                'write_date',
                'customer_rank',  # si es cliente
                'supplier_rank',  # si es proveedor
            ]
            
            customer = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'read',
                [id],
                {'fields': fields}
            )
            
            if customer:
                df = pd.DataFrame([customer[0]])
                return df
            else:
                return "Cliente no encontrado"
            
        except Exception as e:
            return f"Error al leer el cliente: {str(e)}"
    
    def read_all_customers_in_df(self, domain=None, limit=None):
        """
        Lee todos los clientes que coincidan con el dominio especificado
        
        :param domain: Lista de condiciones para filtrar los clientes (opcional)
        :param limit: Número máximo de registros a retornar (opcional)
        :return: DataFrame con los clientes o mensaje de error
        """
        try:
            fields = [
                'id',            # Añadimos el ID del cliente
                'name',
                'vat',
                'email',
                'phone',
                'mobile',
                'street',
                'city',
                'state_id',
                'country_id',
                'company_type',
                'l10n_latam_identification_type_id',
                'create_date',
                'write_date',
                'customer_rank',
                'supplier_rank',
            ]
            
            # Si no se especifica un dominio, usar lista vacía
            domain = domain or [('customer_rank', '>', 0)]  # Por defecto, solo clientes
            
            # Buscar IDs de clientes
            customer_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'search',
                [domain],
                {'limit': limit} if limit else {}
            )
            
            if not customer_ids:
                return "No se encontraron clientes"
            
            # Leer datos de los clientes
            customers = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'read',
                [customer_ids],
                {'fields': fields}
            )
            
            # Convertir a DataFrame
            df = pd.DataFrame(customers)
            return df
            
        except Exception as e:
            return f"Error al leer los clientes: {str(e)}"
    
    def read_customer_by_vat(self, vat):
        """
        Busca un cliente por su RUT/VAT
        
        :param vat: RUT o identificación fiscal del cliente
        :return: DataFrame con los datos del cliente o mensaje de error
        """
        try:
            domain = [
                ('vat', '=', vat),
                ('customer_rank', '>', 0)
            ]
            
            customer_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'search',
                [domain]
            )
            
            if customer_ids:
                return self.read_customer_by_id(customer_ids[0])
            else:
                return "Cliente no encontrado"
            
        except Exception as e:
            return f"Error al buscar el cliente: {str(e)}"

    def read_customer_by_email(self, email):
        """
        Busca un cliente por su email
        
        :param email: Email del cliente
        :return: DataFrame con los datos del cliente o mensaje de error
        """
        try:
            domain = [
                ('email', '=ilike', email), # Usamos ilike para case-insensitive
                ('customer_rank', '>', 0)
            ]
            
            customer_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'search',
                [domain],
                {'limit': 1} # Solo necesitamos el primero que coincida
            )
            
            if customer_ids:
                return self.read_customer_by_id(customer_ids[0])
            else:
                return "Cliente no encontrado"
            
        except Exception as e:
            return f"Error al buscar el cliente por email: {str(e)}"

    def read_customer_by_phone(self, phone):
        """
        Busca un cliente por su número de teléfono (phone o mobile).
        Normaliza el número de entrada a formato chileno 569XXXXXXXX
        y busca coincidencias robustas en Odoo.
        
        :param phone: Número de teléfono del cliente
        :return: DataFrame con los datos del cliente o mensaje de error
        """
        normalized_phone = self._normalize_phone_number_chile(phone)
        
        if not normalized_phone:
             logger.warning(f"<read_customer_by_phone> No se pudo normalizar el teléfono: {phone}")
             return "Cliente no encontrado"

        # Extraer los últimos 9 dígitos para búsqueda flexible
        last_9_digits = normalized_phone[-9:]

        try:
            # Dominio de búsqueda:
            # 1. phone o mobile TERMINA con los últimos 9 dígitos del normalizado
            # 2. O phone o mobile ES EXACTAMENTE el número normalizado
            domain = [
                '&',
                ('customer_rank', '>', 0),
                 '|', 
                     '|',
                         ('phone', 'like', f'%{last_9_digits}'), 
                         ('mobile', 'like', f'%{last_9_digits}'),
                     '|',
                         ('phone', '=', normalized_phone),
                         ('mobile', '=', normalized_phone)
            ]
            
            customer_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'search',
                [domain],
                {'limit': 1} # Solo necesitamos el primero que coincida
            )
            
            if customer_ids:
                # Devolvemos el resultado usando read_customer_by_id
                # Aseguramos que la respuesta sea consistente
                result = self.read_customer_by_id(customer_ids[0])
                # Si read_customer_by_id devuelve el string de error, pasarlo
                if isinstance(result, str):
                    return result 
                # Añadir el teléfono normalizado al resultado para referencia
                if not result.empty:
                    result['normalized_phone_search'] = normalized_phone
                return result
            else:
                return "Cliente no encontrado"
            
        except Exception as e:
            logger.error(f"<read_customer_by_phone> Error al buscar cliente por teléfono {phone} (normalizado: {normalized_phone}): {str(e)}")
            return f"Error al buscar el cliente por teléfono: {str(e)}"
