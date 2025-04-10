from llm import *
from utils import *
from image2text import cogvlm
import argparse
from accelerate import init_empty_weights, infer_auto_device_map, load_checkpoint_and_dispatch
import warnings
warnings.filterwarnings("ignore")

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, default='SHTech',
                        choices=['SHTech', 'avenue', 'ped2', 'UBNormal'])
    parser.add_argument('--induct', action='store_true')
    parser.add_argument('--deduct', action='store_true')
    parser.add_argument('--gpt_deduct_demo', action='store_true')
    parser.add_argument('--b', type = int, default=10)
    parser.add_argument('--bs', type = int, default=1)
    args = parser.parse_args()
    return args


def main():
    args = parse_arguments()
    data_name = args.data
    data_full_name = {'SHTech':'ShanghaiTech', 'avenue':'CUHK Avenue' , 'ped2': 'UCSD Ped2', 'UBNormal': 'UBNormal'}[data_name]
    print(args)

    if args.induct:

        print("Loading CogVLM model...")
        cog_model = AutoModelForCausalLM.from_pretrained(
            'THUDM/cogvlm-chat-hf',
            torch_dtype=torch.float16, # Or torch.float16 if bf16 causes issues
            low_cpu_mem_usage=True,
            device_map='auto', # <<< ENABLE THIS!
            trust_remote_code=True
        ).eval() # <<< REMOVE .to(device)
        print("CogVLM model loading finished (using device_map='auto').")

        #Rule generation:
        objects_list = []
        rule_list = []
        batch = args.b
        batch_size = args.bs
        for i in range(batch):
            print('=====> Image Description:')
            selected_image_paths = random_select_data_without_copy(path=f'/kaggle/working/AnomalyRuler/{data_name}/train.csv', num=batch_size, label=0)
            # Prepend the base path to each image path
            # base_path = '/kaggle/working/AnomalyRuler/'
            selected_image_paths = [f"{path}" for path in selected_image_paths]
            print(selected_image_paths)
            objects = cogvlm(model=cog_model, mode='chat', image_paths=selected_image_paths)
            objects_list.append(objects)
            rule_list.append(gpt_induction(objects, data_full_name))
        gpt_rule_correction(rule_list, batch, data_full_name)
        induction_help = '''
        ==>Induction Help for generating rules by your own: Sometimes the API will not follow the exactly same format required in instructions, 
        you can try multiple times, and adjust the format of rules if needed as in the given example rules for better performance,
        e.g., **Rules for Anomaly Human Activities:**
            1. 
            2. 
        '''
        print(induction_help)

    if args.deduct:
        ## Deduction
        model_id = "mistralai/Mistral-7B-Instruct-v0.2"
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        llm_model = AutoModelForCausalLM.from_pretrained(model_id, low_cpu_mem_usage=True, torch_dtype=torch.float16,
                                                     device_map='auto').eval()

        entries = os.listdir(f'/kaggle/working/AnomalyRuler/{data_name}/modified_test_frame_description')

        for item in entries:
            print(item)
            name = item.split('.')[0]
            labels = pd.read_csv(f'/kaggle/working/AnomalyRuler/{data_name}/test_frame/{name}.csv').iloc[:, 1].tolist()
            mixtral_double_deduct(data_name,f'/kaggle/working/AnomalyRuler/{data_name}/modified_test_frame_description/{name}.txt',
                                                  f'/kaggle/working/AnomalyRuler/rule/rule_{data_name}.txt', tokenizer, llm_model, labels=labels)

        evaluate_from_result(f"/kaggle/working/AnomalyRuler/results/{data_name}")

    if args.gpt_deduct_demo:
        entries = os.listdir(f'{data_name}/modified_test_frame_description')
        # entries[:1] try one file
        for item in entries[:1]:
            print(item)
            name = item.split('.')[0]
            gpt_double_deduction_demo(data_name, f'/kaggle/working/AnomalyRuler/{data_name}/modified_test_frame_description/{name}.txt',
                                          f'/kaggle/working/AnomalyRuler/rule/rule_{data_name}.txt')


if __name__ == "__main__":
    main()
