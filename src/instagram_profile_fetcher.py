import io
import logging
from instaloader import (
    Instaloader, 
    Profile, 
    ProfileNotExistsException,
    PrivateProfileNotFollowedException,
    QueryReturnedBadRequestException,
    ConnectionException
)


class InstagramProfileFetcher:
    """"Classe para coletar dados de perfis do Instagram usando Instaloader."""
    def __init__(self, logger: logging.Logger):
        self.loader = Instaloader()
        self.loader.context.sleep = True
        self.log = logger
    
    def check_rate_limit_in_output(self, error_message: str, captured_output: str = "") -> bool:
        """Verifica se o erro ou saída capturada contém indicadores de rate limit."""
        rate_limit_indicators = [
            "Please wait a few minutes before you try again",
            "429",
            "Too many requests",
            "401 Unauthorized"
        ]
        
        full_text = str(error_message).lower() + " " + captured_output.lower()
        return any(indicator.lower() in full_text for indicator in rate_limit_indicators)
    
    def fetch_profile(self, username: str) -> tuple[dict | None, str, int]:
        """
        Coleta dados de um perfil do Instagram.
        
        Returns:
            tuple: (profile_data, status, penalty)
            - profile_data: dicionário com dados do perfil ou None se houver erro
            - status: status do perfil ('collected', 'profile_not_exists', 'private_profile', etc.)
            - penalty: penalidade a ser adicionada ao contador de requisições
        """
        try:
            self.log.info(f"Coletando dados do perfil: {username}")
            profile_data = Profile.from_username(self.loader.context, username.strip())
            
            data = {
                "username": profile_data.username,
                "full_name": profile_data.full_name,
                "profile_url": f"https://www.instagram.com/{profile_data.username}/",
                "userid": profile_data.userid,
                "biography": profile_data.biography,
                "external_url": profile_data.external_url,
                "followers": profile_data.followers,
                "following": profile_data.followees,
            }
            
            return data, "collected", 1
            
        except ProfileNotExistsException:
            self.log.warning(f"Perfil {username} não existe.")
            return None, "profile_not_exists", 1
            
        except PrivateProfileNotFollowedException:
            self.log.warning(f"Perfil {username} é privado.")
            return None, "private_profile", 1
            
        except (QueryReturnedBadRequestException, ConnectionException) as e:
            self.log.warning(f"Erro de conexão ou requisição para o perfil {username}: {e}")
            return None, "connection_error", 5
            
        except Exception as e:
            # Capturar saída para análise
            stderr_capture = io.StringIO()
            captured_output = stderr_capture.getvalue()
            
            # Verificar se é erro de rate limit
            if self.check_rate_limit_in_output(str(e), captured_output):
                self.log.warning(f"Rate limit detectado ao coletar {username}.")
                return None, "not_collected", 15
            else:
                self.log.error(f"Erro ao coletar dados do perfil {username}: {e}")
                return None, "error", 10