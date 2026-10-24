from selenium import webdriver
from selenium.webdriver.common.by import By
import time

opts = webdriver.EdgeOptions()
opts.add_argument('--headless=new')
opts.add_argument('--disable-gpu')
driver = webdriver.Edge(options=opts)
try:
    driver.get('https://www2.sii.cl/stc/noauthz')
    time.sleep(4)
    inp = driver.find_element(By.CSS_SELECTOR, 'input.rut-form')
    inp.send_keys('76041417-4')
    btn = driver.find_element(By.NAME, 'Consultar')
    driver.execute_script('arguments[0].click();', btn)
    time.sleep(6)
    
    elems = driver.find_elements(By.XPATH, "//*[contains(text(), 'VER ')]")
    print('Elementos VER encontrados:', len(elems))
    for el in elems:
        print('Tag:', el.tag_name, 'Text:', el.text)
        driver.execute_script('arguments[0].click();', el)
    time.sleep(4)
    tables = driver.find_elements(By.TAG_NAME, 'table')
    for idx, t in enumerate(tables):
        print(f'Tabla {idx+1}:', repr(t.text[:150]))
    
    # Imprimir body completo despues de hacer clic
    full_text = driver.find_element(By.TAG_NAME, 'body').text
    print('=== FULL BODY POST CLIC ===')
    print(full_text[-1500:])
except Exception as e:
    print('Error:', e)
finally:
    driver.quit()
